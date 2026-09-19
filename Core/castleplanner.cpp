#include "castleplanner.hpp"
#include "cityfortifications.hpp"
#include "citygeometry.hpp"
#include "numeric.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <string>
#include <system_error>
#include <utility>
#include <vector>
namespace fantasy_world_generator::castleplanner {
namespace {
using settlementpresets::py_repr;

// ---------------------------------------------------------------------------
// Python arithmetic the reference leans on
// ---------------------------------------------------------------------------
// math.degrees multiplies by this constant and math.radians by its reciprocal; neither
// divides, so the two are not exact inverses and the reference depends on that.
constexpr double rad_to_deg=180.0/pi;
constexpr double deg_to_rad=pi/180.0;
double py_degrees(double radians) {return radians*rad_to_deg;}
double py_radians(double degrees) {return degrees*deg_to_rad;}
// round(x) with no digits: C round() (half away from zero), then the halfway case
// redone half-to-even, which is exactly what float.__round__(None) does.
std::int64_t py_round(double value) {
    double rounded=std::round(value);
    if(std::fabs(value-rounded)==0.5) rounded=2.0*std::round(value/2.0);
    return static_cast<std::int64_t>(rounded);
}
// round(x, ndigits) on a float: the decimal round-trip, not nearbyint(x*10^n)/10^n.
double round_to(double value,int digits) {return fortification_round_digits(value,digits);}
// Python's // floors towards negative infinity.
std::int64_t floor_div(std::int64_t value,std::int64_t divisor) {
    std::int64_t quotient=value/divisor;
    if(value%divisor!=0 && ((value<0)!=(divisor<0))) --quotient;
    return quotient;
}
// ... and % follows the divisor's sign.
std::int64_t py_imod(std::int64_t value,std::int64_t divisor) {
    std::int64_t remainder=value%divisor;
    if(remainder!=0 && ((remainder<0)!=(divisor<0))) remainder+=divisor;
    return remainder;
}
// math.dist over two points: CPython's own scaled norm, not the platform hypot.
double py_dist(double ax,double az,double bx,double bz) {
    return python_hypot(ax-bx,az-bz);
}

Value vint(std::int64_t value) {return Value::make_int(value);}
Value vflt(double value) {return Value::make_float(value);}
Value vstr(std::string value) {return Value::make_string(std::move(value));}
Value vbool(bool value) {return Value::make_bool(value);}
Value vnull() {return Value::make_null();}
Value varr() {return Value::make_array();}
Value vobj() {return Value::make_object();}
Value vpair(double a,double b) {
    Value out=varr();out.items.push_back(vflt(a));out.items.push_back(vflt(b));return out;
}
Value vpair(const std::pair<double,double>& point) {return vpair(point.first,point.second);}

double as_number(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole_fits?static_cast<double>(value.whole):value.number;
    if(value.kind==Value::Kind::Float) return value.number;
    if(value.kind==Value::Kind::Bool) return value.boolean?1.:0.;
    throw PlannerError("Expected a numeric value");
}
double field_number(const Value& owner,const std::string& key) {return as_number(owner.at(key));}
const Value* find_field(const Value& owner,const std::string& key) {
    return owner.is_object()?owner.find(key):nullptr;
}
// `int(value)`: an int is itself, a float truncates towards zero.
std::int64_t py_int(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole;
    return static_cast<std::int64_t>(as_number(value));
}
// `str(value)` on the identities this module interpolates.
std::string py_str(const Value& value) {
    switch(value.kind) {
        case Value::Kind::String: return value.text;
        case Value::Kind::Int: return value.whole_fits?std::to_string(value.whole):value.text;
        case Value::Kind::Float: return py_repr(value.number);
        case Value::Kind::Bool: return value.boolean?"True":"False";
        default: return "None";
    }
}
// Python's `==` across the whole JSON tree: it crosses the int/float line and never
// crosses the str line, which is what `other.get('id')==fortress.get('id')` needs when
// one side is a missing key (None) and the other a string.
bool value_equal(const Value& a,const Value& b) {
    const bool a_num=a.is_number()||a.kind==Value::Kind::Bool;
    const bool b_num=b.is_number()||b.kind==Value::Kind::Bool;
    if(a_num&&b_num) {
        if(a.kind==Value::Kind::Int&&b.kind==Value::Kind::Int&&a.whole_fits&&b.whole_fits)
            return a.whole==b.whole;
        return as_number(a)==as_number(b);
    }
    if(a.kind!=b.kind) return false;
    switch(a.kind) {
        case Value::Kind::Null: return true;
        case Value::Kind::String: return a.text==b.text;
        case Value::Kind::Array: {
            if(a.items.size()!=b.items.size()) return false;
            for(std::size_t i=0;i<a.items.size();++i)
                if(!value_equal(a.items[i],b.items[i])) return false;
            return true;
        }
        case Value::Kind::Object: {
            if(a.fields.size()!=b.fields.size()) return false;
            for(const auto& entry:a.fields) {
                const Value* other=b.find(entry.first);
                if(other==nullptr||!value_equal(entry.second,*other)) return false;
            }
            return true;
        }
        default: return false;
    }
}

// ---------------------------------------------------------------------------
// json.dumps(value, sort_keys=True, separators=(',',':'))
//
// NOT settlementpresets::dumps: `planner_identity` leaves ensure_ascii at its default,
// so a non-ASCII character is hashed as its `\uXXXX` escape, and the keys are sorted
// rather than kept in insertion order. Both differences land in the two sha256 sums.
// ---------------------------------------------------------------------------
void escape_ascii(const std::string& value,std::string& out) {
    out+='"';
    for(std::size_t index=0;index<value.size();) {
        const auto c=static_cast<unsigned char>(value[index]);
        if(c<0x80) {
            ++index;
            switch(c) {
                case '\\': out+="\\\\";continue;
                case '"': out+="\\\"";continue;
                case '\b': out+="\\b";continue;
                case '\f': out+="\\f";continue;
                case '\n': out+="\\n";continue;
                case '\r': out+="\\r";continue;
                case '\t': out+="\\t";continue;
                default: break;
            }
            if(c<0x20) {
                char unit[8];
                std::snprintf(unit,sizeof unit,"\\u%04x",static_cast<unsigned>(c));
                out+=unit;
                continue;
            }
            out+=static_cast<char>(c);
            continue;
        }
        // Decode one UTF-8 scalar so it can be written as the \uXXXX escape (and the
        // surrogate pair) CPython's ensure_ascii encoder produces.
        unsigned code=0;
        std::size_t extra=0;
        if((c&0xE0u)==0xC0u) {code=c&0x1Fu;extra=1;}
        else if((c&0xF0u)==0xE0u) {code=c&0x0Fu;extra=2;}
        else {code=c&0x07u;extra=3;}
        ++index;
        for(std::size_t k=0;k<extra&&index<value.size();++k,++index)
            code=(code<<6)|(static_cast<unsigned char>(value[index])&0x3Fu);
        char unit[16];
        if(code>=0x10000u) {
            const unsigned rest=code-0x10000u;
            std::snprintf(unit,sizeof unit,"\\u%04x\\u%04x",0xD800u+(rest>>10),
                          0xDC00u+(rest&0x3FFu));
        } else {
            std::snprintf(unit,sizeof unit,"\\u%04x",code);
        }
        out+=unit;
    }
    out+='"';
}
void dump_sorted(const Value& node,std::string& out) {
    switch(node.kind) {
        case Value::Kind::Null: out+="null";return;
        case Value::Kind::Bool: out+=node.boolean?"true":"false";return;
        case Value::Kind::Int: out+=node.text;return;
        case Value::Kind::Float: out+=py_repr(node.number);return;
        case Value::Kind::String: escape_ascii(node.text,out);return;
        case Value::Kind::Array: {
            out+='[';
            for(std::size_t i=0;i<node.items.size();++i) {
                if(i) out+=',';
                dump_sorted(node.items[i],out);
            }
            out+=']';
            return;
        }
        case Value::Kind::Object: {
            // `sorted(dct.items())` on str keys, which is code-point order; UTF-8 bytes
            // already sort that way, so the plain string compare is the same order.
            std::vector<const std::pair<std::string,Value>*> order;
            order.reserve(node.fields.size());
            for(const auto& entry:node.fields) order.push_back(&entry);
            std::stable_sort(order.begin(),order.end(),
                             [](const std::pair<std::string,Value>* a,
                                const std::pair<std::string,Value>* b) {
                                 return a->first<b->first;
                             });
            out+='{';
            for(std::size_t i=0;i<order.size();++i) {
                if(i) out+=',';
                escape_ascii(order[i]->first,out);
                out+=':';
                dump_sorted(order[i]->second,out);
            }
            out+='}';
            return;
        }
    }
}
std::string dumps_sorted(const Value& value) {
    std::string out;
    dump_sorted(value,out);
    return out;
}

// ---------------------------------------------------------------------------
// random.Random(<sha256 hex digest>)
//
// CPython turns a str seed into `int.from_bytes(text + sha512(text).digest())` and runs
// init_by_array over that integer's little-endian 32-bit words. PyRandom takes a 64-bit
// seed and cannot express a 1024-bit key, so the Twister is rebuilt here. sha512 is not
// in Core either, so it is implemented alongside.
// ---------------------------------------------------------------------------
constexpr std::uint64_t sha512_k[80]={
    0x428a2f98d728ae22ull,0x7137449123ef65cdull,0xb5c0fbcfec4d3b2full,0xe9b5dba58189dbbcull,
    0x3956c25bf348b538ull,0x59f111f1b605d019ull,0x923f82a4af194f9bull,0xab1c5ed5da6d8118ull,
    0xd807aa98a3030242ull,0x12835b0145706fbeull,0x243185be4ee4b28cull,0x550c7dc3d5ffb4e2ull,
    0x72be5d74f27b896full,0x80deb1fe3b1696b1ull,0x9bdc06a725c71235ull,0xc19bf174cf692694ull,
    0xe49b69c19ef14ad2ull,0xefbe4786384f25e3ull,0x0fc19dc68b8cd5b5ull,0x240ca1cc77ac9c65ull,
    0x2de92c6f592b0275ull,0x4a7484aa6ea6e483ull,0x5cb0a9dcbd41fbd4ull,0x76f988da831153b5ull,
    0x983e5152ee66dfabull,0xa831c66d2db43210ull,0xb00327c898fb213full,0xbf597fc7beef0ee4ull,
    0xc6e00bf33da88fc2ull,0xd5a79147930aa725ull,0x06ca6351e003826full,0x142929670a0e6e70ull,
    0x27b70a8546d22ffcull,0x2e1b21385c26c926ull,0x4d2c6dfc5ac42aedull,0x53380d139d95b3dfull,
    0x650a73548baf63deull,0x766a0abb3c77b2a8ull,0x81c2c92e47edaee6ull,0x92722c851482353bull,
    0xa2bfe8a14cf10364ull,0xa81a664bbc423001ull,0xc24b8b70d0f89791ull,0xc76c51a30654be30ull,
    0xd192e819d6ef5218ull,0xd69906245565a910ull,0xf40e35855771202aull,0x106aa07032bbd1b8ull,
    0x19a4c116b8d2d0c8ull,0x1e376c085141ab53ull,0x2748774cdf8eeb99ull,0x34b0bcb5e19b48a8ull,
    0x391c0cb3c5c95a63ull,0x4ed8aa4ae3418acbull,0x5b9cca4f7763e373ull,0x682e6ff3d6b2b8a3ull,
    0x748f82ee5defb2fcull,0x78a5636f43172f60ull,0x84c87814a1f0ab72ull,0x8cc702081a6439ecull,
    0x90befffa23631e28ull,0xa4506cebde82bde9ull,0xbef9a3f7b2c67915ull,0xc67178f2e372532bull,
    0xca273eceea26619cull,0xd186b8c721c0c207ull,0xeada7dd6cde0eb1eull,0xf57d4f7fee6ed178ull,
    0x06f067aa72176fbaull,0x0a637dc5a2c898a6ull,0x113f9804bef90daeull,0x1b710b35131c471bull,
    0x28db77f523047d84ull,0x32caab7b40c72493ull,0x3c9ebe0a15c9bebcull,0x431d67c49c100d4cull,
    0x4cc5d4becb3e42b6ull,0x597f299cfc657e2aull,0x5fcb6fab3ad6faecull,0x6c44198c4a475817ull};
std::uint64_t ror64(std::uint64_t x,int n) {return (x>>n)|(x<<(64-n));}
std::array<unsigned char,64> sha512(const std::string& message) {
    std::uint64_t h[8]={0x6a09e667f3bcc908ull,0xbb67ae8584caa73bull,0x3c6ef372fe94f82bull,
                        0xa54ff53a5f1d36f1ull,0x510e527fade682d1ull,0x9b05688c2b3e6c1full,
                        0x1f83d9abfb41bd6bull,0x5be0cd19137e2179ull};
    std::string data=message;
    const std::uint64_t bits=static_cast<std::uint64_t>(message.size())*8ull;
    data+=static_cast<char>(0x80);
    while(data.size()%128!=112) data+=static_cast<char>(0);
    for(int i=0;i<8;++i) data+=static_cast<char>(0);      // the high half of a 128-bit length
    for(int i=7;i>=0;--i) data+=static_cast<char>((bits>>(8*i))&0xFFull);
    for(std::size_t block=0;block<data.size();block+=128) {
        std::uint64_t w[80];
        for(int i=0;i<16;++i) {
            std::uint64_t value=0;
            for(int b=0;b<8;++b)
                value=(value<<8)|static_cast<unsigned char>(data[block+static_cast<std::size_t>(i*8+b)]);
            w[i]=value;
        }
        for(int i=16;i<80;++i) {
            const std::uint64_t s0=ror64(w[i-15],1)^ror64(w[i-15],8)^(w[i-15]>>7);
            const std::uint64_t s1=ror64(w[i-2],19)^ror64(w[i-2],61)^(w[i-2]>>6);
            w[i]=w[i-16]+s0+w[i-7]+s1;
        }
        std::uint64_t a=h[0],b=h[1],c=h[2],d=h[3],e=h[4],f=h[5],g=h[6],hh=h[7];
        for(int i=0;i<80;++i) {
            const std::uint64_t s1=ror64(e,14)^ror64(e,18)^ror64(e,41);
            const std::uint64_t ch=(e&f)^((~e)&g);
            const std::uint64_t t1=hh+s1+ch+sha512_k[i]+w[i];
            const std::uint64_t s0=ror64(a,28)^ror64(a,34)^ror64(a,39);
            const std::uint64_t maj=(a&b)^(a&c)^(b&c);
            const std::uint64_t t2=s0+maj;
            hh=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        h[0]+=a;h[1]+=b;h[2]+=c;h[3]+=d;h[4]+=e;h[5]+=f;h[6]+=g;h[7]+=hh;
    }
    std::array<unsigned char,64> out{};
    for(int i=0;i<8;++i)
        for(int b=0;b<8;++b)
            out[static_cast<std::size_t>(i*8+b)]=
                static_cast<unsigned char>((h[static_cast<std::size_t>(i)]>>(56-8*b))&0xFFull);
    return out;
}
// The Mersenne Twister CPython seeds from a text key.
class TextRandom {
  public:
    explicit TextRandom(const std::string& text);
    double random();
  private:
    static constexpr std::size_t mt_size=624,mt_shift=397;
    std::uint32_t word();
    std::vector<std::uint32_t> state_;
    std::size_t index_=mt_size;
};
TextRandom::TextRandom(const std::string& text) {
    // `a = int.from_bytes(a.encode() + _sha512(a.encode()).digest())`, big endian.
    std::vector<unsigned char> bytes(text.begin(),text.end());
    const std::array<unsigned char,64> digest=sha512(text);
    bytes.insert(bytes.end(),digest.begin(),digest.end());
    // random_seed() splits |n| into little-endian 32-bit words, keeping
    // `(bit_length - 1) / 32 + 1` of them -- so the leading zero words are dropped, and
    // a zero seed still carries one word.
    std::vector<std::uint32_t> key;
    const std::size_t count=bytes.size();
    for(std::size_t j=0;j*4<count;++j) {
        std::uint32_t value=0;
        for(std::size_t b=0;b<4;++b) {
            const std::size_t at=count-1-(j*4+b);
            if(j*4+b>=count) break;
            value|=static_cast<std::uint32_t>(bytes[at])<<(8*b);
        }
        key.push_back(value);
    }
    while(key.size()>1&&key.back()==0u) key.pop_back();
    if(key.empty()) key.push_back(0u);
    // init_genrand(19650218), then init_by_array over the key.
    std::vector<std::uint32_t> mt(mt_size,0);
    mt[0]=19650218u;
    for(std::size_t i=1;i<mt_size;++i)
        mt[i]=static_cast<std::uint32_t>(1812433253u*(mt[i-1]^(mt[i-1]>>30))+static_cast<std::uint32_t>(i));
    std::size_t i=1,j=0;
    const std::size_t length=key.size();
    for(std::size_t k=std::max(mt_size,length);k;--k) {
        mt[i]=static_cast<std::uint32_t>((mt[i]^((mt[i-1]^(mt[i-1]>>30))*1664525u))
                                         +key[j]+static_cast<std::uint32_t>(j));
        if(++i>=mt_size) {mt[0]=mt[mt_size-1];i=1;}
        if(++j>=length) j=0;
    }
    for(std::size_t k=mt_size-1;k;--k) {
        mt[i]=static_cast<std::uint32_t>((mt[i]^((mt[i-1]^(mt[i-1]>>30))*1566083941u))
                                         -static_cast<std::uint32_t>(i));
        if(++i>=mt_size) {mt[0]=mt[mt_size-1];i=1;}
    }
    mt[0]=0x80000000u;
    state_=std::move(mt);
}
std::uint32_t TextRandom::word() {
    if(index_>=mt_size) {
        for(std::size_t i=0;i<mt_size;++i) {
            const std::uint32_t mixed=(state_[i]&0x80000000u)|(state_[(i+1)%mt_size]&0x7fffffffu);
            state_[i]=state_[(i+mt_shift)%mt_size]^(mixed>>1)^((mixed&1u)?0x9908b0dfu:0u);
        }
        index_=0;
    }
    std::uint32_t y=state_[index_++];
    y^=y>>11;y^=(y<<7)&0x9d2c5680u;y^=(y<<15)&0xefc60000u;y^=y>>18;
    return y;
}
double TextRandom::random() {
    const std::uint32_t a=word()>>5,b=word()>>6;
    return (a*67108864.0+b)*(1.0/9007199254740992.0);
}
std::string hex_digest(const std::string& bytes) {return sha256(bytes);}

// ---------------------------------------------------------------------------
// terrain_detail.HeightField, over the raw rasters rather than a world envelope
// ---------------------------------------------------------------------------
Grid layer_or(const Layer& layer,std::size_t n,double fallback) {
    if(layer.present) return layer.rows;
    return Grid(n,std::vector<double>(n,fallback));
}
Grid value_layer_or(const ValueLayer& layer,std::size_t n,double fallback) {
    if(!layer.present) return Grid(n,std::vector<double>(n,fallback));
    Grid out(layer.rows.size());
    for(std::size_t z=0;z<layer.rows.size();++z) {
        out[z].reserve(layer.rows[z].size());
        for(const Value& v:layer.rows[z]) out[z].push_back(as_number(v));
    }
    return out;
}
class HeightField {
  public:
    explicit HeightField(const World& world);
    bool defined() const {return defined_;}
    double height(const Vec3& p) const;
  private:
    struct Band {double scale,amplitude;std::int64_t seed;};
    static double at(const Grid& h,std::size_t ix,std::size_t iz,std::size_t jz,double fx,double fz) {
        return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz;
    }
    void cell(const Vec3& p,std::size_t& ix,std::size_t& iz,std::size_t& jz,
              double& fx,double& fz) const;
    const Grid* base_=nullptr;
    std::int64_t n_=0;
    bool defined_=false;
    Grid strength_,water_;
    double sea_=0.,radius_=0.;
    std::vector<Band> bands_;
};
HeightField::HeightField(const World& world) {
    base_=&world.height;
    n_=static_cast<std::int64_t>(world.height.size());
    const auto n=static_cast<std::size_t>(n_);
    defined_=world.has_terrain_detail;
    radius_=world.globe_radius;
    sea_=world.sea_level;
    water_=layer_or(world.water_type,n,0.);
    const Grid river=layer_or(world.river,n,0.);
    const Grid flood=layer_or(world.flood_risk,n,0.);
    const Grid biome=value_layer_or(world.natural_biome,n,3.);
    if(defined_)
        for(std::size_t i=0;i<world.bands.size();++i)
            bands_.push_back(Band{world.bands[i].scale_m,world.bands[i].amplitude_m,
                                  static_cast<std::int64_t>(child_seed(
                                      static_cast<std::uint64_t>(world.detail_seed),
                                      std::to_string(i)))});
    // The dict literal the reference indexes by biome code; an absent code is .65.
    auto biome_factor=[](double code) {
        if(code==5.) return 1.4;
        if(code==3.) return .8;
        if(code==4.) return 1.;
        if(code==7.) return 1.;
        if(code==15.) return .8;
        return .65;
    };
    strength_.assign(n,std::vector<double>(n,0.));
    for(std::size_t z=0;z<n;++z)
        for(std::size_t x=0;x<n;++x)
            strength_[z][x]=water_[z][x]!=0.?0.
                :std::max(0.,1-std::min(1.,river[z][x]*2))*std::max(0.,1-std::min(1.,flood[z][x]))
                 *biome_factor(biome[z][x]);
}
void HeightField::cell(const Vec3& p,std::size_t& ix,std::size_t& iz,std::size_t& jz,
                       double& fx,double& fz) const {
    const double span=static_cast<double>(n_-1);
    const double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    ix=static_cast<std::size_t>(x);
    iz=static_cast<std::size_t>(z);
    jz=std::min(static_cast<std::size_t>(n_-1),iz+1);
    fx=x-static_cast<double>(ix);
    fz=z-static_cast<double>(iz);
}
double HeightField::height(const Vec3& p) const {
    if(!defined_) return fantasy_world_generator::sample(*base_,p);
    std::size_t ix=0,iz=0,jz=0;double fx=0.,fz=0.;
    cell(p,ix,iz,jz,fx,fz);
    const double base=at(*base_,ix,iz,jz,fx,fz);
    const double coast=std::max(0.,std::min(1.,(base-sea_)/20.));
    if(coast==0.) return base;
    double strength=at(strength_,ix,iz,jz,fx,fz);
    strength=std::max(0.,(strength-.15)/.85);
    if(strength==0.) return base;
    const double wet=std::max(0.,1-2*at(water_,ix,iz,jz,fx,fz));
    strength*=coast*coast*(3-2*coast)*wet*wet;
    if(strength==0.) return base;
    // `sum(...)` over the bands: CPython's compensated float sum, not a plain +=.
    Sum detail;
    for(const Band& band:bands_)
        detail.add(band.amplitude*perlin3(p[0]*radius_/band.scale,p[1]*radius_/band.scale,
                                          p[2]*radius_/band.scale,band.seed));
    return base+strength*detail.value();
}

// ---------------------------------------------------------------------------
// castle_planner._sampler
//
// A value-identical duplicate of city_planner._sampler. The Core city planner keeps its
// copy file-private, so this is a second port rather than a call; the harness proves the
// two REFERENCE samplers agree, which is the claim that matters.
// ---------------------------------------------------------------------------
struct SampleResult {
    bool water=false;
    double slope=0.,flood=0.,height=0.,moisture=0.,biome=0.,variant=0.;
    std::int64_t gx=0,gz=0;
};
class Sampler {
  public:
    Sampler(const World& world,const Value& site,double half);
    SampleResult sample(double x,double z,bool with_slope=true) const;
  private:
    double river_distance(double x,double z) const;
    Vec3 direction_at(double x,double z) const;
    const World* world_=nullptr;
    std::int64_t n_=0;
    double radius_=0.;
    Vec3 up_{},east_{},north_{};
    HeightField field_;
    std::vector<std::array<double,4>> lines_;
};
Sampler::Sampler(const World& world,const Value& site,double half)
        : world_(&world),n_(world.size),radius_(world.globe_radius),field_(world) {
    const double span=static_cast<double>(n_-1);
    const double lat=pi/2-pi*field_number(site,"z")/span;
    const double lon=-pi+2*pi*field_number(site,"x")/span;
    up_=Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
    east_=Vec3{-std::sin(lon),0.,std::cos(lon)};
    north_=Vec3{-std::sin(lat)*std::cos(lon),std::cos(lat),-std::sin(lat)*std::sin(lon)};
    auto local=[&](const std::pair<std::int64_t,std::int64_t>& node,double& ox,double& oz) {
        const double la=pi/2-pi*static_cast<double>(node.second)/span;
        const double lo=-pi+2*pi*static_cast<double>(node.first)/span;
        const Vec3 p{std::cos(la)*std::cos(lo),std::sin(la),std::cos(la)*std::sin(lo)};
        const double den=dot(p,up_);
        if(den<=.1) return false;
        ox=radius_*dot(p,east_)/den;
        oz=radius_*dot(p,north_)/den;
        return true;
    };
    for(const auto& segment:world.river_segments) {
        const auto count=static_cast<std::int64_t>(world.water_nodes.size());
        if(segment.first<0||segment.first>=count||segment.second<0||segment.second>=count)
            throw PlannerError("list index out of range");
        double ax=0.,az=0.,bx=0.,bz=0.;
        if(!local(world.water_nodes[static_cast<std::size_t>(segment.first)],ax,az)) continue;
        if(!local(world.water_nodes[static_cast<std::size_t>(segment.second)],bx,bz)) continue;
        const double lo0=std::min(ax,bx),hi0=std::max(ax,bx);
        const double lo1=std::min(az,bz),hi1=std::max(az,bz);
        if(lo0<=half+40&&hi0>=-half-40&&lo1<=half+40&&hi1>=-half-40)
            lines_.push_back({ax,az,bx,bz});
    }
}
double Sampler::river_distance(double x,double z) const {
    double best=1e30;
    for(const auto& line:lines_) {
        const double dx=line[2]-line[0],dz=line[3]-line[1];
        const double square=dx*dx+dz*dz;
        // `(dx*dx+dz*dz or 1)`: an exactly zero length divides by one instead.
        const double denominator=square!=0.?square:1.;
        const double raw=((x-line[0])*dx+(z-line[1])*dz)/denominator;
        const double t=std::max(0.,std::min(1.,raw));
        best=std::min(best,python_hypot(x-line[0]-t*dx,z-line[1]-t*dz));
    }
    return best;
}
Vec3 Sampler::direction_at(double x,double z) const {
    Vec3 p{};
    for(int i=0;i<3;++i) p[i]=up_[i]+(east_[i]*x+north_[i]*z)/radius_;
    return unit(p);
}
SampleResult Sampler::sample(double x,double z,bool with_slope) const {
    const double span=static_cast<double>(n_-1);
    Vec3 p{};
    for(int i=0;i<3;++i) p[i]=up_[i]+(east_[i]*x+north_[i]*z)/radius_;
    p=unit(p);
    SampleResult out;
    // round() then % on Python ints: banker's rounding, then a floored modulo.
    out.gx=py_imod(py_round((std::atan2(p[2],p[0])+pi)/(2*pi)*span),n_-1);
    // The reference does NOT clamp before asin here, unlike HeightField._cell.
    out.gz=std::max<std::int64_t>(0,std::min<std::int64_t>(
        n_-1,py_round((pi/2-std::asin(p[1]))/pi*span)));
    const auto gx=static_cast<std::size_t>(out.gx);
    const auto gz=static_cast<std::size_t>(out.gz);
    const double distance=river_distance(x,z);
    out.slope=world_->slope.present?world_->slope.rows[gz][gx]:0.;
    if(field_.defined()&&with_slope) {
        const double dx=(field_.height(direction_at(x+1,z))-field_.height(direction_at(x-1,z)))/2;
        const double dz=(field_.height(direction_at(x,z+1))-field_.height(direction_at(x,z-1)))/2;
        out.slope=py_degrees(std::atan(python_hypot(dx,dz)));
    }
    const double water=world_->water_type.present?world_->water_type.rows[gz][gx]:0.;
    out.water=water!=0.||distance<12;
    const double river=world_->river.present?world_->river.rows[gz][gx]:0.;
    out.flood=(!lines_.empty()&&river>.5)?(distance<28?1.:0.)
              :(world_->flood_risk.present?world_->flood_risk.rows[gz][gx]:0.);
    out.height=field_.height(p);
    out.moisture=world_->moisture.present?world_->moisture.rows[gz][gx]:.5;
    out.biome=world_->natural_biome.present?as_number(world_->natural_biome.rows[gz][gx]):3.;
    out.variant=world_->biome_variant.present?as_number(world_->biome_variant.rows[gz][gx]):-1.;
    return out;
}

// ---------------------------------------------------------------------------
// The castle registry
// ---------------------------------------------------------------------------
std::string& mutable_path() {
    static std::string path="Sim/icarus_sim/castles.json";
    return path;
}
std::string read_text(const std::string& path) {
    std::ifstream stream(std::filesystem::u8path(path),std::ios::binary);
    if(!stream) throw PlannerError("Cannot read castle registry: "+path);
    return std::string((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());
}
const Value& castles_document() {
    struct Key {
        std::string path;
        std::int64_t mtime=0;
        std::uintmax_t size=0;
        bool operator<(const Key& other) const {
            if(path!=other.path) return path<other.path;
            if(mtime!=other.mtime) return mtime<other.mtime;
            return size<other.size;
        }
    };
    static std::map<Key,Value> cache;
    const std::string path=mutable_path();
    Key key;
    key.path=path;
    std::error_code code;
    const std::filesystem::path handle=std::filesystem::u8path(path);
    key.size=std::filesystem::file_size(handle,code);
    if(code) key.size=0;
    const auto stamp=std::filesystem::last_write_time(handle,code);
    key.mtime=code?0:static_cast<std::int64_t>(stamp.time_since_epoch().count());
    const auto found=cache.find(key);
    if(found!=cache.end()) return found->second;
    Value data=settlementpresets::loads(read_text(path));
    const Value* schema=data.is_object()?data.find("schema"):nullptr;
    const Value* version=data.is_object()?data.find("schema_version"):nullptr;
    if(schema==nullptr||!schema->is_string()
       ||schema->text!="fantasy-world-generator.castle-registry"
       ||version==nullptr||version->kind!=Value::Kind::Int||version->whole!=1)
        throw PlannerError("Unsupported castle registry schema");
    // `type(...) is not int`: a float revision fails even when it is whole, and so does
    // a bool, because `type(True)` is `bool`.
    const Value* revision=data.find("revision");
    if(revision==nullptr||revision->kind!=Value::Kind::Int||!revision->whole_fits
       ||revision->whole<1)
        throw PlannerError("Invalid castle registry revision");
    return cache.emplace(key,std::move(data)).first->second;
}

// ---------------------------------------------------------------------------
// castle_geometry reports, rendered back into the dicts the reference embeds
// ---------------------------------------------------------------------------
Value segment_value(const CastleSegment& segment) {
    Value out=vobj();
    out.set("id",vstr(segment.id));
    out.set("ring_id",vstr(segment.ring_id));
    out.set("structure_id",vstr(segment.structure_id));
    out.set("module_id",vstr(segment.module_id));
    out.set("from_m",vpair(segment.from_m));
    out.set("to_m",vpair(segment.to_m));
    out.set("center_m",vpair(segment.center_m));
    out.set("length_m",vflt(segment.length_m));
    out.set("rotation_degrees",vflt(segment.rotation_degrees));
    out.set("thickness_m",vflt(segment.thickness_m));
    out.set("height_m",vflt(segment.height_m));
    out.set("walkway",vbool(segment.walkway));
    return out;
}
Value ring_node_value(const CastleRingNode& node) {
    Value out=vobj();
    out.set("id",vstr(node.id));
    out.set("kind",vstr(node.kind));
    out.set("position_m",vpair(node.position_m));
    out.set("ring_id",vstr(node.ring_id));
    return out;
}
Value join_value(const CastleJoinNode& join) {
    Value out=vobj();
    out.set("id",vstr(join.id));
    out.set("ring_id",vstr(join.ring_id));
    out.set("module_key",vstr(join.module_key));
    out.set("module_id",vstr(join.module_id));
    out.set("structure_id",vstr(join.structure_id));
    out.set("position_m",vpair(join.position_m));
    if(join.has_approach) out.set("approach_m",vpair(join.approach_m));
    if(join.has_thickness) out.set("thickness_m",vflt(join.thickness_m));
    out.set("height_m",vflt(join.height_m));
    if(join.has_curtain_height) out.set("curtain_height_m",vflt(join.curtain_height_m));
    out.set("walkway",vbool(join.walkway));
    if(!join.kind.empty()) out.set("kind",vstr(join.kind));
    return out;
}
Value join_list(const std::vector<CastleJoinNode>& joins) {
    Value out=varr();
    for(const CastleJoinNode& join:joins) out.items.push_back(join_value(join));
    return out;
}
Value network_value(const CastleWallNetwork& net) {
    Value out=vobj();
    out.set("id",vstr(net.id));
    out.set("role",vstr(net.role));
    Value polyline=varr();
    for(const auto& point:net.polyline_m) polyline.items.push_back(vpair(point));
    out.set("polyline_m",std::move(polyline));
    out.set("status",vstr(net.status));
    Value segments=varr();
    for(const CastleSegment& segment:net.segments) segments.items.push_back(segment_value(segment));
    out.set("segments",std::move(segments));
    Value nodes=varr();
    for(const CastleRingNode& node:net.nodes) nodes.items.push_back(ring_node_value(node));
    out.set("nodes",std::move(nodes));
    out.set("gates",join_list(net.gates));
    out.set("towers",join_list(net.towers));
    out.set("stairs",join_list(net.stairs));
    out.set("walkway_continuous",vbool(net.walkway_continuous));
    Value unplaced=varr();
    for(const CastleUnplaced& entry:net.unplaced) {
        Value row=vobj();
        row.set("building_id",entry.has_building_id?vstr(entry.building_id):vnull());
        row.set("reason",vstr(entry.reason));
        unplaced.items.push_back(std::move(row));
    }
    out.set("unplaced",std::move(unplaced));
    // `report.update(...)` appends these three only when the ring closes; a broken ring
    // simply does not carry them, and the record shows that.
    if(net.has_counts) {
        out.set("segment_count",vint(net.segment_count));
        out.set("gate_count",vint(net.gate_count));
        out.set("ditch",vbool(net.ditch));
    }
    return out;
}
// The `modules` table and `join_rules` block, as the accepted geometry port takes them.
CastleModule parse_module(const Value& value) {
    CastleModule module;
    const Value* id=find_field(value,"id");
    if(id!=nullptr&&id->is_string()) module.id=id->text;
    const Value* structure=find_field(value,"structure_id");
    if(structure!=nullptr&&structure->is_string()) module.structure_id=structure->text;
    const Value* role=find_field(value,"role");
    if(role!=nullptr&&role->is_string()) module.role=role->text;
    const Value* end=find_field(value,"end_type");
    if(end!=nullptr&&end->is_string()) {module.has_end_type=true;module.end_type=end->text;}
    for(int which=0;which<2;++which) {
        const Value* block=find_field(value,which==0?"thickness_m":"height_m");
        if(block==nullptr||!block->is_object()) continue;
        const Value* nominal=block->find("nominal");
        if(nominal==nullptr||!nominal->is_number()) continue;
        if(which==0) {module.has_thickness=true;module.thickness_nominal=as_number(*nominal);}
        else {module.has_height=true;module.height_nominal=as_number(*nominal);}
    }
    const Value* walkway=find_field(value,"walkway");
    if(walkway!=nullptr&&walkway->kind!=Value::Kind::Null) {
        module.has_walkway=true;
        module.walkway=walkway->kind==Value::Kind::Bool?walkway->boolean:as_number(*walkway)!=0.;
    }
    const Value* ends=find_field(value,"compatible_ends");
    if(ends!=nullptr&&ends->is_array())
        for(const Value& item:ends->items) module.compatible_ends.push_back(item.text);
    return module;
}
std::map<std::string,CastleModule> parse_modules(const Value& table) {
    std::map<std::string,CastleModule> modules;
    for(const auto& entry:table.fields) modules.emplace(entry.first,parse_module(entry.second));
    return modules;
}
CastleJoinRules parse_rules(const Value& value) {
    CastleJoinRules rules;
    rules.max_thickness_delta_m=field_number(value,"max_thickness_delta_m");
    rules.max_height_delta_m=field_number(value,"max_height_delta_m");
    rules.min_turn_degrees_for_corner=field_number(value,"min_turn_degrees_for_corner");
    rules.max_turn_degrees=field_number(value,"max_turn_degrees");
    rules.segment_depth_m=field_number(value,"segment_depth_m");
    const Value* walkway=find_field(value,"walkway_required");
    rules.walkway_required=walkway!=nullptr&&walkway->kind==Value::Kind::Bool&&walkway->boolean;
    return rules;
}
CastleRingSpec parse_ring_spec(const Value& value) {
    CastleRingSpec spec;
    const Value* gate=find_field(value,"gate");
    if(gate!=nullptr&&gate->is_string()) spec.gate=gate->text;
    const Value* postern=find_field(value,"postern");
    spec.postern=postern!=nullptr&&(postern->kind==Value::Kind::Bool?postern->boolean
                                                                   :as_number(*postern)!=0.);
    const Value* stairs=find_field(value,"stairs");
    spec.stairs=stairs!=nullptr?py_int(*stairs):0;
    const Value* budget=find_field(value,"tower_budget");
    spec.tower_budget=budget!=nullptr?py_int(*budget):4;
    const Value* ditch=find_field(value,"ditch");
    spec.ditch=ditch!=nullptr&&(ditch->kind==Value::Kind::Bool?ditch->boolean
                                                             :as_number(*ditch)!=0.);
    return spec;
}
// `sum(r['target'] for r in ...)`: an all-int roster is exact integer arithmetic, so it
// stays in int64; a float target would switch CPython to the compensated float loop,
// which is what the Sum branch reproduces.
Value staff_total(const Value& row) {
    const Value* staffing=find_field(row,"staffing");
    const Value* roles=staffing!=nullptr?find_field(*staffing,"roles"):nullptr;
    if(roles==nullptr||!roles->is_array()) return vint(0);
    std::int64_t whole=0;
    bool exact=true;
    Sum total;
    for(const Value& role:roles->items) {
        const Value& target=role.at("target");
        if(exact&&target.kind==Value::Kind::Int&&target.whole_fits) {whole+=target.whole;continue;}
        if(exact) {exact=false;total.add(static_cast<double>(whole));}
        total.add(as_number(target));
    }
    return exact?vint(whole):vflt(total.value());
}
}

void set_castles_path(const std::string& path) {mutable_path()=path;}
const std::string& castles_path() {return mutable_path();}
const Value& load_castles() {return castles_document();}

Value castle_structures() {
    const Value library=settlementpresets::section("structure_blocks").at("castle");
    Value out=vobj();
    for(const Value& block:library.at("blocks").items)
        for(const Value& structure:block.at("structures").items)
            out.set(structure.at("id").text,structure);
    return out;
}

Value planner_identity() {
    const Value& doc=load_castles();
    const Value structures=castle_structures();
    Value out=vobj();
    out.set("version",vint(planner_version));
    out.set("geometry_version",vint(castle_geometry_version));
    out.set("castles_sha256",vstr(hex_digest(dumps_sorted(doc))));
    out.set("castle_buildings_sha256",vstr(hex_digest(dumps_sorted(structures))));
    return out;
}

const Value& select_kit(const Value& kits,std::int64_t seed,const std::string& fortress_id) {
    const std::string label=std::to_string(seed)+":castle-kit:"+fortress_id;
    TextRandom rng(hex_digest(label));
    // `max(1, int(k.get('weight', 1)))`, accumulated as Python ints and only then
    // floated by `cum_weights[-1] + 0.0`.
    std::vector<std::int64_t> cumulative;
    std::int64_t running=0;
    for(const Value& kit:kits.items) {
        const Value* weight=find_field(kit,"weight");
        const std::int64_t value=weight!=nullptr?py_int(*weight):1;
        running+=value>1?value:1;
        cumulative.push_back(running);
    }
    if(cumulative.empty()) throw PlannerError("Total of weights must be greater than zero");
    const double total=static_cast<double>(cumulative.back())+0.0;
    if(!(total>0.)) throw PlannerError("Total of weights must be greater than zero");
    const double target=rng.random()*total;
    // bisect_right(cum_weights, target, 0, len(population) - 1).
    std::size_t lo=0,hi=cumulative.size()-1;
    while(lo<hi) {
        const std::size_t mid=(lo+hi)/2;
        if(target<static_cast<double>(cumulative[mid])) hi=mid;
        else lo=mid+1;
    }
    return kits.items[lo];
}

SupportApproach support_approach(const World& world,const Value& fortress,std::int64_t half) {
    SupportApproach out;
    out.entries=varr();
    const Value* access=find_field(fortress,"access_nodes");
    std::vector<std::int64_t> path;
    if(access!=nullptr&&access->is_array())
        for(const Value& node:access->items) path.push_back(py_int(node));
    if(path.size()<2||world.water_nodes.empty()) return out;
    sceneframe::World scene;
    scene.size=world.size;
    scene.config_globe_radius=world.globe_radius;
    const sceneframe::Site site{field_number(fortress,"x"),field_number(fortress,"z"),
                                sceneframe::identity_text(py_str(fortress.at("id")))};
    const sceneframe::Frame f=sceneframe::frame(scene,site);
    const double r=f.radius;
    const auto count=static_cast<std::int64_t>(world.water_nodes.size());
    double prev[2]={0.,0.};
    const double half_m=static_cast<double>(half);
    for(std::size_t k=1;k<path.size();++k) {
        const std::int64_t index=path[k];
        if(index<0||index>=count) break;
        const auto& node=world.water_nodes[static_cast<std::size_t>(index)];
        const Vec3 p=direction(node.first,node.second,world.size);
        // Three-term compensated dot products, not plain accumulation.
        const double den=dot(p,f.up);
        if(den<=0.) break;
        const double q[2]={r*dot(p,f.east)/den,r*dot(p,f.north)/den};
        if(std::max(std::fabs(q[0]),std::fabs(q[1]))>half_m) {
            bool have=false;
            double t=0.;
            for(int j=0;j<2;++j) {
                if(!(std::fabs(q[j])>half_m)) continue;
                const double denominator=q[j]-prev[j];
                if(denominator==0.) throw sceneframe::ZeroDivision();
                const double candidate=((q[j]>0.?half_m:-half_m)-prev[j])/denominator;
                if(!have||candidate<t) {t=candidate;have=true;}
            }
            // The crossing is interpolated on both axes even though only the exceeding
            // one chose `t`.
            out.has_approach=true;
            out.x=prev[0]+t*(q[0]-prev[0]);
            out.z=prev[1]+t*(q[1]-prev[1]);
            const std::string id=py_str(fortress.at("id"));
            const Vec3 heading=sceneframe::local_direction(f,out.x,out.z);
            Value entry=vobj();
            entry.set("route_id",vstr("support:"+id));
            entry.set("route_index",vint(-1));
            entry.set("end",vstr("to"));
            entry.set("outside_index",vint(0));
            entry.set("junction_id",vstr("junction:"+id+":support"));
            entry.set("gate_local_m",vpair(out.x,out.z));
            Value facing=varr();
            for(int i=0;i<3;++i) facing.items.push_back(vflt(heading[i]));
            entry.set("direction",std::move(facing));
            entry.set("status",vstr("unreachable"));
            entry.set("reason",
                      vstr("No terrain-safe street connection to parent-city approach"));
            out.entries.items.push_back(std::move(entry));
            break;
        }
        prev[0]=q[0];prev[1]=q[1];
    }
    return out;
}

Value sample_probe(const World& world,const Value& fortress,double half,
                   const std::vector<Probe>& probes) {
    const Sampler sampler(world,fortress,half);
    Value out=varr();
    for(const Probe& probe:probes) {
        const SampleResult v=sampler.sample(probe.x,probe.z,probe.with_slope);
        const auto gx=static_cast<std::size_t>(v.gx);
        const auto gz=static_cast<std::size_t>(v.gz);
        Value row=varr();
        row.items.push_back(vbool(v.water));
        row.items.push_back(vflt(v.slope));
        row.items.push_back(vflt(v.flood));
        row.items.push_back(vflt(v.height));
        row.items.push_back(world.natural_biome.present?world.natural_biome.rows[gz][gx]:vint(3));
        row.items.push_back(world.biome_variant.present?world.biome_variant.rows[gz][gx]:vint(-1));
        out.items.push_back(std::move(row));
    }
    return out;
}

Value plan_castle(const World& world,const Value& fortress) {
    const Value& doc=load_castles();
    const Value structures=castle_structures();
    const Value& modules_table=doc.at("modules");
    const std::map<std::string,CastleModule> modules=parse_modules(modules_table);
    const CastleJoinRules rules=parse_rules(doc.at("join_rules"));
    const Value& kit=select_kit(doc.at("kits"),world.seed,py_str(fortress.at("id")));
    const std::int64_t n=world.size;
    const double span=static_cast<double>(n-1);
    const double radius=world.globe_radius;
    double half_value=field_number(kit,"half_m");
    // Bound by parent city and neighbouring fortresses without moving anchors.
    const double fortress_x=field_number(fortress,"x");
    const double fortress_z=field_number(fortress,"z");
    const Value missing=vnull();
    const Value* fortress_id=find_field(fortress,"id");
    std::vector<const Value*> sites;
    for(const Value& site:world.sites) sites.push_back(&site);
    for(const Value& other:world.fortresses) {
        // `other is fortress` first, then the id comparison; the reference skips on
        // either, and a fortress that is not this one but shares its id is skipped too.
        if(&other==&fortress) continue;
        const Value* other_id=find_field(other,"id");
        if(value_equal(other_id!=nullptr?*other_id:missing,
                       fortress_id!=nullptr?*fortress_id:missing)) continue;
        sites.push_back(&other);
    }
    for(const Value* other:sites) {
        const double lat1=pi/2-pi*fortress_z/span;
        const double lat2=pi/2-pi*field_number(*other,"z")/span;
        const double dl=2*pi*(field_number(*other,"x")-fortress_x)/span;
        const double cosine=std::sin(lat1)*std::sin(lat2)+std::cos(lat1)*std::cos(lat2)*std::cos(dl);
        const double distance=radius*std::acos(std::max(-1.,std::min(1.,cosine)));
        half_value=std::min(half_value,distance*.28);
    }
    // `max(CELL, int(half / CELL) * CELL)`: int() truncates towards zero, so the floor
    // has to come from the division being exact, not from a cast of a floor().
    const std::int64_t quantised=static_cast<std::int64_t>(half_value/static_cast<double>(planner_cell))
                                 *planner_cell;
    const std::int64_t half=std::max<std::int64_t>(planner_cell,quantised);
    const std::int64_t size=floor_div(2*half,planner_cell);
    const double half_m=static_cast<double>(half);
    const double cell_m=static_cast<double>(planner_cell);
    const Sampler sampler(world,fortress,half_m);

    Value terrain_codes=varr(),terrain_biomes=varr(),terrain_variants=varr();
    std::set<Cell> valid;
    std::map<Cell,double> heights,slopes;
    for(std::int64_t j=0;j<size;++j) {
        Value row=varr(),biome_row=varr(),mutation_row=varr();
        for(std::int64_t i=0;i<size;++i) {
            const SampleResult v=sampler.sample(-half_m+(static_cast<double>(i)+.5)*cell_m,
                                                -half_m+(static_cast<double>(j)+.5)*cell_m);
            heights.emplace(Cell(i,j),v.height);
            slopes.emplace(Cell(i,j),v.slope);
            const std::int64_t code=v.water?1:(v.slope>25||v.flood>.65?2:0);
            row.items.push_back(vint(code));
            const auto gx=static_cast<std::size_t>(v.gx);
            const auto gz=static_cast<std::size_t>(v.gz);
            biome_row.items.push_back(world.natural_biome.present
                ?world.natural_biome.rows[gz][gx]:vint(3));
            mutation_row.items.push_back(world.biome_variant.present
                ?world.biome_variant.rows[gz][gx]:vint(-1));
            if(code==0) valid.emplace(i,j);
        }
        terrain_codes.items.push_back(std::move(row));
        terrain_biomes.items.push_back(std::move(biome_row));
        terrain_variants.items.push_back(std::move(mutation_row));
    }
    const std::int64_t surface_size=size+1;
    Value surface=vobj();
    surface.set("size",vint(surface_size));
    surface.set("step_m",vflt(static_cast<double>(2*half)/static_cast<double>(surface_size-1)));
    Value heights_m=varr();
    for(std::int64_t j=0;j<surface_size;++j) {
        Value row=varr();
        for(std::int64_t i=0;i<surface_size;++i) {
            // `i * 2 * half` is an exact integer product in the reference, divided once.
            const double sx=-half_m+static_cast<double>(i*2*half)/static_cast<double>(surface_size-1);
            const double sz=-half_m+static_cast<double>(j*2*half)/static_cast<double>(surface_size-1);
            row.items.push_back(vflt(round_to(sampler.sample(sx,sz,false).height,4)));
        }
        heights_m.items.push_back(std::move(row));
    }
    surface.set("heights_m",std::move(heights_m));

    Value result=vobj();
    result.set("version",vint(planner_version));
    result.set("kind",vstr("castle"));
    result.set("fortress_id",fortress.at("id"));
    const Value* core=find_field(fortress,"core_id");
    result.set("core_id",core!=nullptr?*core:vnull());
    result.set("x",fortress.at("x"));
    result.set("z",fortress.at("z"));
    result.set("kit_id",kit.at("id"));
    result.set("kit_name",kit.at("name"));
    Value bounds=varr();
    bounds.items.push_back(vint(-half));bounds.items.push_back(vint(-half));
    bounds.items.push_back(vint(half));bounds.items.push_back(vint(half));
    result.set("bounds_m",std::move(bounds));
    static const char* phase_order[]={"map","kit","perimeter","courts","landmarks","services"};
    Value passes=varr();
    for(const char* phase:phase_order) {
        Value entry=vobj();
        entry.set("id",vstr(phase));
        entry.set("placed",vint(0));
        passes.items.push_back(std::move(entry));
    }
    result.set("passes",std::move(passes));
    result.set("plots",varr());
    result.set("roads",varr());
    result.set("wall_networks",varr());
    result.set("unplaced",varr());
    result.set("road_connections",varr());
    Value warnings=varr();
    warnings.items.push_back(vstr("Schematic fortification modules; structural engineering "
                                  "and garrison beds are not resolved."));
    warnings.items.push_back(vstr("Curtain segments are metre-scale wall runs; production "
                                  "ARCH meshes remain unassigned."));
    result.set("warnings",std::move(warnings));
    result.set("stats",vobj());
    result.set("debug",vobj());
    result.set("status",vstr("unbuildable"));
    result.set("source_resolution_m",vflt(round_to(pi*radius/span,4)));
    Value terrain=vobj();
    terrain.set("cell_m",vint(planner_cell));
    terrain.set("size",vint(size));
    terrain.set("codes",std::move(terrain_codes));
    terrain.set("surface",std::move(surface));
    terrain.set("natural_biome",std::move(terrain_biomes));
    terrain.set("biome_variant",std::move(terrain_variants));
    terrain.set("biome_catalogue",world.biome_catalogue.is_array()?world.biome_catalogue:varr());
    terrain.set("magical_catalogue",world.magical_catalogue.is_array()?world.magical_catalogue:varr());
    Value magic_colors=vobj();
    for(const auto& entry:world.magic_colors) magic_colors.set(entry.first,entry.second);
    terrain.set("magic_colors",std::move(magic_colors));
    result.set("terrain",std::move(terrain));

    Value& passes_out=*result.find("passes");
    Value& plots_out=*result.find("plots");
    Value& unplaced_out=*result.find("unplaced");
    passes_out.items[0].set("placed",vint(1));
    if(valid.size()<24) {
        Value row=vobj();
        row.set("building_id",vstr("building.curtain_segment"));
        row.set("count",vint(1));
        row.set("reason",vstr("Insufficient buildable land for a fortress precinct"));
        unplaced_out.items.push_back(std::move(row));
        return result;
    }
    passes_out.items[1].set("placed",vint(1));
    const SupportApproach approach=support_approach(world,fortress,half);
    result.set("road_connections",approach.entries);
    const double rx=half_m*0.72;
    const double rz=half_m*0.62;
    std::vector<CastleWallNetwork> networks;
    const Value& rings=kit.at("rings");
    for(std::size_t ring_i=0;ring_i<rings.items.size();++ring_i) {
        const Value& ring_spec_value=rings.items[ring_i];
        const double scale=field_number(ring_spec_value,"scale");
        const std::string role=ring_spec_value.at("role").text;
        const std::string ring_id="ring-"+role;
        const std::vector<std::pair<double,double>> raw=ellipse_ring(rx*scale,rz*scale,32);
        std::vector<std::pair<double,double>> polyline=
            clip_ring_to_valid(raw,valid,half_m,planner_cell,25,slopes);
        // Fall back to the unclipped ellipse when terrain clipping collapses the ring.
        if(polyline.size()<8) polyline=raw;
        CastleApproach ring_approach;
        if(ring_i==0&&approach.has_approach) {
            ring_approach.set=true;
            ring_approach.value={approach.x,approach.z};
        }
        const CastleRingSpec spec=parse_ring_spec(ring_spec_value);
        const CastleWallNetwork network=build_wall_network(ring_id,role,polyline,ring_approach,
                                                           spec,modules,rules,spec.ditch);
        networks.push_back(network);
        if(network.status!="closed")
            for(const CastleUnplaced& u:network.unplaced) {
                Value row=vobj();
                // `u.get('building_id', 'building.curtain_segment')`: a key that is
                // PRESENT and None stays None; only a missing key takes the default.
                row.set("building_id",u.has_building_id?vstr(u.building_id):vnull());
                row.set("count",vint(1));
                row.set("reason",vstr(u.reason));
                unplaced_out.items.push_back(std::move(row));
            }
    }
    Value wall_networks=varr();
    for(const CastleWallNetwork& net:networks) wall_networks.items.push_back(network_value(net));
    result.set("wall_networks",std::move(wall_networks));
    std::int64_t closed=0;
    for(const CastleWallNetwork& net:networks) if(net.status=="closed") ++closed;
    passes_out.items[2].set("placed",vint(closed));
    if(closed==0) {
        result.set("status",vstr("partial"));
        Value stats=vobj();
        stats.set("wall_rings_closed",vint(0));
        stats.set("segments",vint(0));
        stats.set("plots",vint(0));
        stats.set("workers",vint(0));
        result.set("stats",std::move(stats));
        return result;
    }

    // `install(...)`: one plot row, plus the pass counter the reference bumps by name.
    auto install=[&](const std::string& structure_id,double x,double z,bool degrees_is_zero,
                     double degrees,const char* phase,const char* kind) {
        const Value& row=structures.at(structure_id);
        const Value& plot_m=row.at("plot_m");
        const double width=field_number(plot_m,"width");
        const double depth=field_number(plot_m,"depth");
        const double rad=py_radians(degrees_is_zero?0.:degrees);
        const double c=std::cos(rad),s=std::sin(rad);
        const double offsets[4][2]={{-width/2,-depth/2},{width/2,-depth/2},
                                    {width/2,depth/2},{-width/2,depth/2}};
        double lowest=0.,highest=0.;
        for(int corner=0;corner<4;++corner) {
            const double u=offsets[corner][0],v=offsets[corner][1];
            const double ground=sampler.sample(x+u*c-v*s,z+u*s+v*c).height;
            if(corner==0) {lowest=ground;highest=ground;continue;}
            lowest=std::min(lowest,ground);
            highest=std::max(highest,ground);
        }
        Value plot=vobj();
        plot.set("id",vstr("plot-"+std::to_string(plots_out.items.size())));
        plot.set("building_id",vstr(structure_id));
        plot.set("name",row.at("name"));
        plot.set("kind",vstr(kind));
        plot.set("phase",vstr(phase));
        plot.set("x_m",vflt(round_to(x,2)));
        plot.set("z_m",vflt(round_to(z,2)));
        // `round(0, 4)` on the literal int the reference passes for every axis-aligned
        // plot is the INT 0, which json writes as `0` and not `0.0`.
        // `round(0, 4)` on the literal int the reference passes for every axis-aligned
        // plot is the INT 0, which json writes as `0` and not `0.0`.
        plot.set("rotation_degrees",degrees_is_zero?vint(0):vflt(round_to(degrees,4)));
        plot.set("ground_elevation_m",vflt(round_to(highest,4)));
        plot.set("foundation_bottom_m",vflt(round_to(lowest,4)));
        plot.set("plot_m",plot_m);
        plot.set("dimensions_m",row.at("dimensions_m"));
        Value access=varr();
        access.items.push_back(vflt(round_to(x,2)));
        access.items.push_back(vflt(round_to(z,2)));
        plot.set("road_access",std::move(access));
        plot.set("workers",staff_total(row));
        plot.set("beds",vint(0));
        plots_out.items.push_back(std::move(plot));
        for(Value& pass:passes_out.items)
            if(pass.at("id").text==phase) {
                pass.set("placed",vint(pass.at("placed").whole+1));
                break;
            }
    };

    // `{n['role']: n['polyline_m'] for n in networks if closed}`: a repeated role keeps
    // its first position and its last polyline, which only the lookup cares about.
    std::map<std::string,const std::vector<std::pair<double,double>>*> ring_polylines;
    for(const CastleWallNetwork& net:networks)
        if(net.status=="closed") ring_polylines[net.role]=&net.polyline_m;
    // `sum(p[0] for p in ring) / len(ring)`: a float sum, so Neumaier compensated.
    auto centroid=[](const std::vector<std::pair<double,double>>& ring,double& cx,double& cz) {
        Sum sx,sz;
        for(const auto& point:ring) sx.add(point.first);
        for(const auto& point:ring) sz.add(point.second);
        const auto count=static_cast<double>(ring.size());
        cx=sx.value()/count;
        cz=sz.value()/count;
    };
    struct Placement {const char* phase;const char* kind;const char* noun;};
    const Placement court_kind{"courts","court","court"};
    const Placement landmark_kind{"landmarks","landmark","keep"};
    for(int which=0;which<2;++which) {
        const Placement& shape=which==0?court_kind:landmark_kind;
        const Value* list=find_field(kit,which==0?"courts":"landmarks");
        if(list==nullptr||!list->is_array()) continue;
        for(const Value& entry:list->items) {
            const std::string role=entry.at("ring_role").text;
            const std::string structure_id=entry.at("structure_id").text;
            const auto found=ring_polylines.find(role);
            // `if not ring`: a missing role AND an empty polyline both fall through.
            if(found==ring_polylines.end()||found->second->empty()) {
                Value row=vobj();
                row.set("building_id",vstr(structure_id));
                row.set("count",vint(1));
                row.set("reason",vstr("No closed ring "+role+" for "+shape.noun));
                unplaced_out.items.push_back(std::move(row));
                continue;
            }
            double cx=0.,cz=0.;
            centroid(*found->second,cx,cz);
            install(structure_id,cx,cz,true,0.,shape.phase,shape.kind);
        }
    }

    // Place services around the primary bailey centre, offset from the keep.
    const CastleWallNetwork& primary=networks[0];
    if(primary.status=="closed") {
        double cx=0.,cz=0.;
        centroid(primary.polyline_m,cx,cz);
        double angle0=0.0;
        if(approach.has_approach) angle0=std::atan2(approach.z-cz,approach.x-cx);
        std::int64_t service_i=0;
        const Value* services=find_field(kit,"services");
        if(services!=nullptr&&services->is_array())
            for(const Value& service:services->items) {
                const std::string sid=service.at("structure_id").text;
                if(!structures.has(sid)) {
                    Value row=vobj();
                    row.set("building_id",vstr(sid));
                    row.set("count",vint(1));
                    row.set("reason",vstr("Unknown castle structure"));
                    unplaced_out.items.push_back(std::move(row));
                    continue;
                }
                if(sid=="building.drawbridge") {
                    // castle_planner.py:327 already proved this ring closed, so the
                    // report DOES carry 'ditch'; this is not a missing-key read.
                    if(!(primary.has_counts&&primary.ditch)||primary.gates.empty()) {
                        Value row=vobj();
                        row.set("building_id",vstr(sid));
                        row.set("count",vint(1));
                        row.set("reason",vstr("Drawbridge requires outer ditch and gate"));
                        unplaced_out.items.push_back(std::move(row));
                        continue;
                    }
                    const CastleJoinNode& gate=primary.gates.front();
                    install(sid,gate.position_m.first+std::cos(angle0)*10,
                            gate.position_m.second+std::sin(angle0)*10,
                            false,py_degrees(angle0),"services","service");
                    continue;
                }
                if(sid=="building.barbican") {
                    bool already=false;
                    for(const CastleJoinNode& gate:primary.gates)
                        if(gate.structure_id=="building.barbican") {already=true;break;}
                    if(already) continue;   // Already represented as the gate node.
                }
                const Value* count=find_field(service,"count");
                const std::int64_t repeats=count!=nullptr?py_int(*count):1;
                for(std::int64_t repeat=0;repeat<repeats;++repeat) {
                    const double ang=angle0+pi*0.5+static_cast<double>(service_i)*(pi*0.35);
                    const double dist=half_m*0.22;
                    install(sid,cx+std::cos(ang)*dist,cz+std::sin(ang)*dist,
                            false,py_degrees(ang+pi/2),"services","service");
                    ++service_i;
                }
            }
    }

    // Emit gate/tower/stair plots for consumers that only read plots[].
    for(const CastleWallNetwork& net:networks) {
        if(net.status!="closed") continue;
        for(const CastleJoinNode& gate:net.gates) {
            bool duplicate=false;
            for(const Value& plot:plots_out.items)
                if(plot.at("building_id").text==gate.structure_id
                   &&py_dist(as_number(plot.at("x_m")),as_number(plot.at("z_m")),
                             gate.position_m.first,gate.position_m.second)<1.) {
                    duplicate=true;break;
                }
            if(duplicate) continue;
            install(gate.structure_id,gate.position_m.first,gate.position_m.second,
                    true,0.,"perimeter","gate");
        }
        for(const CastleJoinNode& tower:net.towers)
            install(tower.structure_id,tower.position_m.first,tower.position_m.second,
                    true,0.,"perimeter","tower");
        for(const CastleJoinNode& stair:net.stairs)
            install(stair.structure_id,stair.position_m.first,stair.position_m.second,
                    true,0.,"perimeter","stair");
    }

    // `sum(p['workers'] for p in result['plots'])`: the same int/float split as the
    // roster totals it adds up.
    std::int64_t workers=0;
    bool workers_exact=true;
    Sum worker_total;
    for(const Value& plot:plots_out.items) {
        const Value& count=plot.at("workers");
        if(workers_exact&&count.kind==Value::Kind::Int&&count.whole_fits) {
            workers+=count.whole;
            continue;
        }
        if(workers_exact) {workers_exact=false;worker_total.add(static_cast<double>(workers));}
        worker_total.add(as_number(count));
    }
    std::int64_t segment_total=0;
    for(const CastleWallNetwork& net:networks)
        segment_total+=static_cast<std::int64_t>(net.segments.size());
    bool walkway=true;
    for(const CastleWallNetwork& net:networks)
        if(net.status=="closed"&&!net.walkway_continuous) {walkway=false;break;}
    Value stats=vobj();
    stats.set("wall_rings_closed",vint(closed));
    stats.set("segments",vint(segment_total));
    stats.set("plots",vint(static_cast<std::int64_t>(plots_out.items.size())));
    stats.set("workers",workers_exact?vint(workers):vflt(worker_total.value()));
    stats.set("kit_id",kit.at("id"));
    stats.set("walkway_continuous",vbool(walkway));
    stats.set("unplaced_total",vint(static_cast<std::int64_t>(unplaced_out.items.size())));
    result.set("stats",std::move(stats));
    result.set("status",vstr(closed==static_cast<std::int64_t>(rings.items.size())
                             &&unplaced_out.items.empty()?"complete":"partial"));
    Value debug=vobj();
    debug.set("valid_cells",vint(static_cast<std::int64_t>(valid.size())));
    debug.set("approach_m",approach.has_approach?vpair(approach.x,approach.z):vnull());
    debug.set("geometry_version",vint(castle_geometry_version));
    result.set("debug",std::move(debug));
    return result;
}

Value fill_castles(const World& world) {
    // `sorted(..., key=lambda f: str(f['id']))`: Python's sort is stable, so two
    // fortresses spelling the same id keep their list order.
    std::vector<std::size_t> order(world.fortresses.size());
    for(std::size_t i=0;i<order.size();++i) order[i]=i;
    std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
        return py_str(world.fortresses[a].at("id"))<py_str(world.fortresses[b].at("id"));
    });
    Value castles=varr();
    for(const std::size_t index:order)
        castles.items.push_back(plan_castle(world,world.fortresses[index]));
    Value out=vobj();
    out.set("version",vint(planner_version));
    out.set("identity",planner_identity());
    out.set("castles",std::move(castles));
    Value phases=varr();
    for(const char* phase:{"map","kit","perimeter","courts","landmarks","services"})
        phases.items.push_back(vstr(phase));
    out.set("phase_order",std::move(phases));
    out.set("limits",vstr("Schematic fortification modules and bailey plots; not "
                          "structural engineering or production art."));
    return out;
}
}
