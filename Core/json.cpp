#include "json.hpp"

namespace fantasy_world_generator::json {
namespace {
void require(bool ok) { if (!ok) throw Error("INVALID_INPUT"); }
bool digit(char c) { return c>='0' && c<='9'; }
unsigned hex(char c) {
    if(c>='0' && c<='9') return static_cast<unsigned>(c-'0');
    if(c>='a' && c<='f') return static_cast<unsigned>(c-'a'+10);
    if(c>='A' && c<='F') return static_cast<unsigned>(c-'A'+10);
    throw Error("INVALID_INPUT");
}
std::uint32_t scalar(const std::string& text,std::size_t& pos) {
    require(pos<text.size());
    auto first=static_cast<unsigned char>(text[pos++]);
    if(first<128) return first;
    unsigned following=0; std::uint32_t value=0,minimum=0;
    if(first>=0xc2 && first<=0xdf) {following=1;value=first&31;minimum=0x80;}
    else if(first>=0xe0 && first<=0xef) {following=2;value=first&15;minimum=0x800;}
    else if(first>=0xf0 && first<=0xf4) {following=3;value=first&7;minimum=0x10000;}
    else throw Error("INVALID_INPUT");
    for(unsigned i=0;i<following;++i) {
        require(pos<text.size());auto c=static_cast<unsigned char>(text[pos++]);
        require((c&0xc0)==0x80);value=(value<<6)|(c&63);
    }
    require(value>=minimum && value<=0x10ffff && !(value>=0xd800 && value<=0xdfff));
    return value;
}
void append_utf8(std::string& out,std::uint32_t c) {
    if(c<0x80) out+=static_cast<char>(c);
    else if(c<0x800) {out+=static_cast<char>(0xc0|(c>>6));out+=static_cast<char>(0x80|(c&63));}
    else if(c<0x10000) {out+=static_cast<char>(0xe0|(c>>12));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
    else {out+=static_cast<char>(0xf0|(c>>18));out+=static_cast<char>(0x80|((c>>12)&63));out+=static_cast<char>(0x80|((c>>6)&63));out+=static_cast<char>(0x80|(c&63));}
}
struct Parser {
    const std::string& raw; std::size_t pos=0,nodes=0;
    void space() {while(pos<raw.size() && (raw[pos]==' ' || raw[pos]=='\t' || raw[pos]=='\r' || raw[pos]=='\n')) ++pos;}
    bool take(char c) {if(pos<raw.size() && raw[pos]==c) {++pos;return true;} return false;}
    void node(std::size_t depth) {require(depth<=max_depth && ++nodes<=max_nodes);}
    std::uint32_t hex4() {
        require(raw.size()-pos>=4);std::uint32_t n=0;
        for(int i=0;i<4;++i) n=(n<<4)|hex(raw[pos++]);
        return n;
    }
    std::string text() {
        require(take('"'));std::string result;
        while(pos<raw.size()) {
            if(take('"')) return result;
            if(take('\\')) {
                require(pos<raw.size());char c=raw[pos++];
                switch(c) {
                    case '"':case '\\':case '/': result+=c;break;
                    case 'b': result+='\b';break; case 'f':result+='\f';break;
                    case 'n':result+='\n';break;case 'r':result+='\r';break;case 't':result+='\t';break;
                    case 'u': {
                        auto cp=hex4();
                        if(cp>=0xd800 && cp<=0xdbff) {
                            require(take('\\') && take('u'));auto low=hex4();require(low>=0xdc00 && low<=0xdfff);
                            cp=0x10000+((cp-0xd800)<<10)+(low-0xdc00);
                        } else require(!(cp>=0xdc00 && cp<=0xdfff));
                        append_utf8(result,cp);break;
                    }
                    default:throw Error("INVALID_INPUT");
                }
            } else {
                auto cp=scalar(raw,pos);require(cp>=32);append_utf8(result,cp);
            }
            require(result.size()<=max_text_bytes);
        }
        throw Error("INVALID_INPUT");
    }
    Value value(std::size_t depth=0) {
        node(depth);space();require(pos<raw.size());
        if(raw[pos]=='"') return Value(text());
        if(take('[')) {
            Value::Array items;space();if(take(']')) return Value(items);
            do {items.push_back(value(depth+1));space();if(take(']')) return Value(std::move(items));require(take(','));} while(true);
        }
        if(take('{')) {
            Value::Object items;space();if(take('}')) return Value(items);
            do {
                space();node(depth+1);auto key=text();space();require(take(':'));
                auto item=value(depth+1);require(items.emplace(std::move(key),std::move(item)).second);
                space();if(take('}')) return Value(std::move(items));require(take(','));
            } while(true);
        }
        for(const auto& literal: {std::string("null"),std::string("true"),std::string("false")}) {
            if(raw.compare(pos,literal.size(),literal)==0) {
                pos+=literal.size();if(literal=="null") return Value();return Value(literal=="true");
            }
        }
        bool negative=take('-');require(pos<raw.size() && digit(raw[pos]));
        std::int64_t n=0;std::size_t start=pos;
        while(pos<raw.size() && digit(raw[pos])) {
            require(pos-start<16);int d=raw[pos++]-'0';require(n<=(max_safe-d)/10);n=n*10+d;
        }
        require(pos-start==1 || raw[start]!='0');
        // Delimiters are checked by the enclosing container or top-level parser.
        return Value(negative ? -n : n);
    }
};
void escape16(std::string& out,std::uint32_t cp) {
    constexpr char digits[]="0123456789abcdef";out+="\\u";
    for(int shift=12;shift>=0;shift-=4) out+=digits[(cp>>shift)&15];
}
void quote(std::string& out,const std::string& text) {
    require(text.size()<=max_text_bytes);out+='"';std::size_t pos=0;
    while(pos<text.size()) {
        auto cp=scalar(text,pos);
        switch(cp) {
            case '"':out+="\\\"";break;case '\\':out+="\\\\";break;
            case '\b':out+="\\b";break;case '\f':out+="\\f";break;
            case '\n':out+="\\n";break;case '\r':out+="\\r";break;case '\t':out+="\\t";break;
            default:
                if(cp>=32 && cp<127) out+=static_cast<char>(cp);
                else if(cp<=0xffff) escape16(out,cp);
                else {cp-=0x10000;escape16(out,0xd800+(cp>>10));escape16(out,0xdc00+(cp&1023));}
        }
    }
    out+='"';
}
struct Writer {
    std::string out;std::size_t nodes=0;
    void node(std::size_t depth) {require(depth<=max_depth && ++nodes<=max_nodes);}
    void write(const Value& v,std::size_t depth=0) {
        node(depth);
        if(is_null(v)) out+="null";
        else if(auto b=std::get_if<bool>(&v.data)) out+=*b ? "true":"false";
        else if(auto n=std::get_if<std::int64_t>(&v.data)) {
            require(*n>=-max_safe && *n<=max_safe);out+=std::to_string(*n);
        } else if(auto s=std::get_if<std::string>(&v.data)) quote(out,*s);
        else if(auto a=std::get_if<Value::Array>(&v.data)) {
            out+='[';bool first=true;
            for(const auto& item:*a) {if(!first) out+=',';first=false;write(item,depth+1);} out+=']';
        } else {
            out+='{';bool first=true;
            // Valid UTF-8 has the same lexicographic order as Unicode scalars.
            for(const auto& pair:object(v)) {
                if(!first) out+=',';
                first=false;node(depth+1);quote(out,pair.first);out+=':';write(pair.second,depth+1);
            } out+='}';
        }
        require(out.size()<=max_bytes);
    }
};
}
Value parse(const std::string& bytes) {
    require(bytes.size()<=max_bytes);Parser parser{bytes};auto v=parser.value();parser.space();require(parser.pos==bytes.size());
    canonical(v);return v;
}
std::string canonical(const Value& value) {Writer writer;writer.write(value);return writer.out;}
const Value::Object& object(const Value& value) {auto p=std::get_if<Value::Object>(&value.data);require(p!=nullptr);return *p;}
const Value::Array& array(const Value& value) {auto p=std::get_if<Value::Array>(&value.data);require(p!=nullptr);return *p;}
const std::string& string(const Value& value) {auto p=std::get_if<std::string>(&value.data);require(p!=nullptr);return *p;}
std::int64_t integer(const Value& value) {auto p=std::get_if<std::int64_t>(&value.data);require(p!=nullptr);require(*p>=-max_safe && *p<=max_safe);return *p;}
bool is_null(const Value& value) {return std::holds_alternative<std::nullptr_t>(value.data);}
const Value& field(const Value& value,const std::string& key) {const auto& o=object(value);auto p=o.find(key);require(p!=o.end());return p->second;}
void exact(const Value& value,std::initializer_list<const char*> fields) {const auto& o=object(value);require(o.size()==fields.size());for(auto key:fields) require(o.count(key)==1);}
}
