#include "pyrandom.hpp"
#include "numeric.hpp"
#include <algorithm>
#include <cmath>
namespace fantasy_world_generator {
namespace {
constexpr std::size_t mt_size=624, mt_shift=397;
constexpr std::uint32_t mt_matrix=0x9908b0dfu, mt_upper=0x80000000u, mt_lower=0x7fffffffu;
constexpr double two_pi=6.283185307179586476925286766559;
// CPython splits the seed integer into little-endian 32-bit words and runs
// init_by_array over all of them. A seed that fits in 32 bits therefore uses a
// one-word key, which is what every child_seed caller passes, but the city and
// hamlet street seeds take sha256(...)[:8] and are 33 to 64 bits wide. Truncating
// those to 32 bits does not perturb the stream slightly, it replaces it: seed
// 919926291273832743 gives .6393547588299053 where its low word gives
// .9842694628304446.
std::vector<std::uint32_t> python_key(std::uint64_t seed) {
    if(seed==0) return {0u};
    std::vector<std::uint32_t> key;
    for(std::uint64_t rest=seed;rest!=0;rest>>=32)
        key.push_back(static_cast<std::uint32_t>(rest&0xffffffffu));
    return key;
}
std::vector<std::uint32_t> seeded(const std::vector<std::uint32_t>& key) {
    std::vector<std::uint32_t> mt(mt_size,0);
    mt[0]=19650218u;
    for(std::size_t i=1;i<mt_size;++i)
        mt[i]=static_cast<std::uint32_t>(1812433253u*(mt[i-1]^(mt[i-1]>>30))+static_cast<std::uint32_t>(i));
    // init_by_array proper: k counts down from max(624, key_length), and j walks the
    // key, wrapping. With a one-word key this reduces exactly to the previous loop.
    std::size_t i=1,j=0;
    const std::size_t length=key.size();
    for(std::size_t k=std::max(mt_size,length);k;--k) {
        mt[i]=static_cast<std::uint32_t>((mt[i]^((mt[i-1]^(mt[i-1]>>30))*1664525u))+key[j]+static_cast<std::uint32_t>(j));
        if(++i>=mt_size) {mt[0]=mt[mt_size-1];i=1;}
        if(++j>=length) j=0;
    }
    for(std::size_t k=mt_size-1;k;--k) {
        mt[i]=static_cast<std::uint32_t>((mt[i]^((mt[i-1]^(mt[i-1]>>30))*1566083941u))-static_cast<std::uint32_t>(i));
        if(++i>=mt_size) {mt[0]=mt[mt_size-1];i=1;}
    }
    mt[0]=mt_upper;
    return mt;
}
std::uint32_t hex_prefix(const std::string& hex) {
    std::uint32_t value=0;
    for(std::size_t i=0;i<8;++i) {
        const char c=hex[i];
        value=(value<<4)|static_cast<std::uint32_t>(c<='9' ? c-'0' : c-'a'+10);
    }
    return value;
}
}
PyRandom::PyRandom(std::uint64_t seed) : state_(seeded(python_key(seed))),index_(mt_size) {}
std::uint32_t PyRandom::word() {
    if(index_>=mt_size) {
        for(std::size_t i=0;i<mt_size;++i) {
            const std::uint32_t mixed=(state_[i]&mt_upper)|(state_[(i+1)%mt_size]&mt_lower);
            state_[i]=state_[(i+mt_shift)%mt_size]^(mixed>>1)^((mixed&1u) ? mt_matrix : 0u);
        }
        index_=0;
    }
    std::uint32_t y=state_[index_++];
    y^=y>>11;y^=(y<<7)&0x9d2c5680u;y^=(y<<15)&0xefc60000u;y^=y>>18;
    return y;
}
double PyRandom::next() {
    const std::uint32_t a=word()>>5,b=word()>>6;
    return (a*67108864.0+b)*(1.0/9007199254740992.0);
}
double PyRandom::uniform(double low,double high) {return low+(high-low)*next();}
double PyRandom::gauss(double mu,double sigma) {
    if(spare_ready_) {spare_ready_=false;return mu+spare_*sigma;}
    const double angle=next()*two_pi,radius=std::sqrt(-2.0*std::log(1.0-next()));
    spare_=std::sin(angle)*radius;spare_ready_=true;
    return mu+std::cos(angle)*radius*sigma;
}
std::uint64_t PyRandom::getrandbits(int bits) {
    if(bits<=0) return 0;
    if(bits<=32) return word()>>(32-bits);
    std::uint64_t value=0;
    int remaining=bits;
    for(int shift=0;remaining>0;shift+=32,remaining-=32) {
        std::uint32_t chunk=word();
        if(remaining<32) chunk>>=(32-remaining);
        value|=static_cast<std::uint64_t>(chunk)<<shift;
    }
    return value;
}
std::uint64_t PyRandom::randbelow(std::uint64_t bound) {
    if(bound==0) return 0;
    int bits=0;
    for(std::uint64_t value=bound;value;value>>=1) ++bits;
    std::uint64_t drawn=getrandbits(bits);
    while(drawn>=bound) drawn=getrandbits(bits);
    return drawn;
}
std::int64_t PyRandom::randrange(std::int64_t start,std::int64_t stop) {
    return start+static_cast<std::int64_t>(randbelow(static_cast<std::uint64_t>(stop-start)));
}
std::int64_t PyRandom::randint(std::int64_t low,std::int64_t high) {return randrange(low,high+1);}
std::size_t PyRandom::choice(std::size_t count) {return static_cast<std::size_t>(randbelow(count));}
std::size_t PyRandom::weighted_choice(const std::vector<double>& weights) {
    std::vector<double> cumulative(weights.size(),0.);
    double running=0.;
    for(std::size_t i=0;i<weights.size();++i) {running+=weights[i];cumulative[i]=running;}
    const double total=cumulative.back()+0.0;
    const double target=next()*total;
    std::size_t index=0;
    while(index+1<weights.size() && cumulative[index]<=target) ++index;
    return index;
}
std::vector<std::size_t> PyRandom::sample_indices(std::size_t n,std::size_t k) {
    std::vector<std::size_t> result;
    if(k>n) return result;
    result.reserve(k);
    // setsize = 21 + 4**ceil(log(3k, 4)) for k > 5, computed in integers. The float
    // form cannot disagree: 3k is never a power of four, because 3 does not divide
    // any power of four, so the logarithm is never exactly an integer and there is
    // no boundary for a last-ulp error to fall on.
    std::uint64_t setsize=21;
    if(k>5) {
        std::uint64_t power=1;
        while(power<3ull*static_cast<std::uint64_t>(k)) power<<=2;
        setsize+=power;
    }
    if(static_cast<std::uint64_t>(n)<=setsize) {
        // Pool branch: swap the chosen index out and the tail element in.
        std::vector<std::size_t> pool(n);
        for(std::size_t i=0;i<n;++i) pool[i]=i;
        for(std::size_t i=0;i<k;++i) {
            // randbelow(1) is not free: it draws one bit and rejects until it is
            // zero, so the stream advances. Never special-case a bound of one.
            const std::size_t j=static_cast<std::size_t>(randbelow(n-i));
            result.push_back(pool[j]);
            pool[j]=pool[n-i-1];
        }
        return result;
    }
    // Selection-set branch: redraw on collision. The Python `selected` set is only
    // ever tested for membership, never iterated, so a flat bitmap is exact.
    std::vector<bool> seen(n,false);
    for(std::size_t i=0;i<k;++i) {
        std::size_t j=static_cast<std::size_t>(randbelow(n));
        while(seen[j]) j=static_cast<std::size_t>(randbelow(n));
        seen[j]=true;
        result.push_back(j);
    }
    return result;
}
std::uint32_t child_seed_text(const std::string& master,const std::string& domain,std::uint64_t variation) {
    return hex_prefix(sha256("tectonics-v1:"+master+":"+domain+":"+std::to_string(variation)));
}
std::uint32_t child_seed(std::uint64_t master,const std::string& domain,std::uint64_t variation) {
    return child_seed_text(std::to_string(master),domain,variation);
}
}
