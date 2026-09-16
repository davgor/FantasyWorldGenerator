#include "numeric.hpp"
#include <array>
#include <limits>

namespace mathlab {
namespace {
// SHA-256 constants and recurrence: NIST FIPS 180-4 sections 4.2.2, 5.3.3, 6.2.
constexpr std::array<std::uint32_t,64> constants{{
0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2}};
std::uint32_t rotate(std::uint32_t x,unsigned n) {return (x>>n)|(x<<(32-n));}
void numeric_version(std::int64_t version) {
    if(version<0 || version>max_safe) throw Error("INVALID_INPUT");
    if(version!=1) throw Error("UNSUPPORTED_VERSION");
}
std::uint64_t word_value(const std::string& word) {
    if(word.size()!=16) throw Error("INVALID_INPUT");
    std::uint64_t value=0;
    for(char c:word) {
        unsigned d=0;
        if(c>='0' && c<='9') d=static_cast<unsigned>(c-'0');
        else if(c>='a' && c<='f') d=static_cast<unsigned>(c-'a'+10);
        else throw Error("INVALID_INPUT");
        value=(value<<4)|d;
    }
    return value;
}
void network_word(std::string& bytes,std::uint64_t word) {for(int shift=56;shift>=0;shift-=8) bytes+=static_cast<char>((word>>shift)&255);}
}
std::string sha256(const std::string& bytes) {
    if(bytes.size()>json::max_bytes) throw Error("INVALID_INPUT");
    std::string message=bytes;message+=static_cast<char>(0x80);
    while(message.size()%64!=56) message+='\0';
    network_word(message,static_cast<std::uint64_t>(bytes.size())*8);
    std::array<std::uint32_t,8> state{{0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19}};
    for(std::size_t offset=0;offset<message.size();offset+=64) {
        std::array<std::uint32_t,64> w{};
        for(unsigned i=0;i<16;++i) for(unsigned j=0;j<4;++j) w[i]=(w[i]<<8)|static_cast<unsigned char>(message[offset+4*i+j]);
        for(unsigned i=16;i<64;++i) {
            auto s0=rotate(w[i-15],7)^rotate(w[i-15],18)^(w[i-15]>>3);
            auto s1=rotate(w[i-2],17)^rotate(w[i-2],19)^(w[i-2]>>10);
            w[i]=w[i-16]+s0+w[i-7]+s1;
        }
        auto a=state[0],b=state[1],c=state[2],d=state[3],e=state[4],f=state[5],g=state[6],h=state[7];
        for(unsigned i=0;i<64;++i) {
            auto s1=rotate(e,6)^rotate(e,11)^rotate(e,25);
            auto choice=(e&f)^((~e)&g);
            auto t1=h+s1+choice+constants[i]+w[i];
            auto s0=rotate(a,2)^rotate(a,13)^rotate(a,22);
            auto majority=(a&b)^(a&c)^(b&c);
            auto t2=s0+majority;
            h=g;g=f;f=e;e=d+t1;d=c;c=b;b=a;a=t1+t2;
        }
        state[0]+=a;state[1]+=b;state[2]+=c;state[3]+=d;state[4]+=e;state[5]+=f;state[6]+=g;state[7]+=h;
    }
    constexpr char hex[]="0123456789abcdef";std::string result;
    for(auto word:state) for(int shift=28;shift>=0;shift-=4) result+=hex[(word>>shift)&15];
    return result;
}
std::string digest(const json::Value& value) {return sha256(json::canonical(value));}
std::string random_word(const std::string& seed,const std::string& stream,std::int64_t index,std::int64_t version) {
    numeric_version(version);auto seed_value=word_value(seed);
    if(stream.empty() || stream.size()>64 || stream[0]<'a' || stream[0]>'z' || index<0 || index>max_safe) throw Error("INVALID_INPUT");
    for(char c:stream) if(!((c>='a' && c<='z') || (c>='0' && c<='9') || c=='.' || c=='_' || c=='-')) throw Error("INVALID_INPUT");
    std::string frame="MathLab/stream/v1";frame+='\0';network_word(frame,seed_value);
    frame+=static_cast<char>(stream.size());frame+=stream;network_word(frame,static_cast<std::uint64_t>(index));
    return sha256(frame).substr(0,16);
}
double unit_float(const std::string& word,std::int64_t version) {
    static_assert(std::numeric_limits<double>::is_iec559 && std::numeric_limits<double>::digits==53,"numeric v1 requires binary64 double");
    numeric_version(version);return static_cast<double>(word_value(word)>>11)/9007199254740992.0;
}
}
