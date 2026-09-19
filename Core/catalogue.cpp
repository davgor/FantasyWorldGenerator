#include "catalogue.hpp"
#include "counter.hpp"
#include <cmath>
#include <cstdlib>
namespace fantasy_world_generator::catalogue {
namespace {
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
struct Reader {
    const std::string& raw;
    std::size_t pos=0,nodes=0;
    void space() {while(pos<raw.size() && (raw[pos]==' '||raw[pos]=='\t'||raw[pos]=='\r'||raw[pos]=='\n')) ++pos;}
    bool take(char c) {if(pos<raw.size() && raw[pos]==c) {++pos;return true;} return false;}
    void expect(char c) {require(take(c));}
    void node(std::size_t depth) {require(depth<=max_depth && ++nodes<=max_nodes);}
    unsigned hex_quad() {
        require(pos+4<=raw.size());
        unsigned code=0;
        for(int i=0;i<4;++i) {
            const char digit=raw[pos++];
            code<<=4;
            if(digit>='0'&&digit<='9') code|=static_cast<unsigned>(digit-'0');
            else if(digit>='a'&&digit<='f') code|=static_cast<unsigned>(digit-'a'+10);
            else if(digit>='A'&&digit<='F') code|=static_cast<unsigned>(digit-'A'+10);
            else throw Error("INVALID_INPUT");
        }
        return code;
    }
    static void append_utf8(std::string& out,unsigned code) {
        if(code<0x80) {out+=static_cast<char>(code);return;}
        if(code<0x800) {
            out+=static_cast<char>(0xC0|(code>>6));
            out+=static_cast<char>(0x80|(code&0x3F));
            return;
        }
        if(code<0x10000) {
            out+=static_cast<char>(0xE0|(code>>12));
            out+=static_cast<char>(0x80|((code>>6)&0x3F));
            out+=static_cast<char>(0x80|(code&0x3F));
            return;
        }
        require(code<=0x10FFFF);
        out+=static_cast<char>(0xF0|(code>>18));
        out+=static_cast<char>(0x80|((code>>12)&0x3F));
        out+=static_cast<char>(0x80|((code>>6)&0x3F));
        out+=static_cast<char>(0x80|(code&0x3F));
    }
    std::string string_value() {
        expect('"');
        std::string out;
        while(true) {
            require(pos<raw.size() && out.size()<=max_text_bytes);
            const char c=raw[pos++];
            if(c=='"') break;
            if(c!='\\') {out+=c;continue;}
            require(pos<raw.size());
            const char escape=raw[pos++];
            switch(escape) {
                case '"': out+='"';break;
                case '\\': out+='\\';break;
                case '/': out+='/';break;
                case 'b': out+='\b';break;
                case 'f': out+='\f';break;
                case 'n': out+='\n';break;
                case 'r': out+='\r';break;
                case 't': out+='\t';break;
                case 'u': {
                    // Authoring text is not ASCII: creature and place names carry
                    // accents, and a name is display text a consumer shows, so it is
                    // decoded to UTF-8 rather than refused or flattened.
                    unsigned code=hex_quad();
                    if(code>=0xD800 && code<=0xDBFF) {
                        require(pos+2<=raw.size() && raw[pos]=='\\' && raw[pos+1]=='u');
                        pos+=2;
                        const unsigned low=hex_quad();
                        require(low>=0xDC00 && low<=0xDFFF);
                        code=0x10000+((code-0xD800)<<10)+(low-0xDC00);
                    }
                    require(!(code>=0xDC00 && code<=0xDFFF));
                    append_utf8(out,code);
                    break;
                }
                default: throw Error("INVALID_INPUT");
            }
        }
        return out;
    }
    double number_value() {
        const std::size_t start=pos;
        if(pos<raw.size() && (raw[pos]=='-'||raw[pos]=='+')) ++pos;
        while(pos<raw.size() && (std::isdigit(static_cast<unsigned char>(raw[pos])) || raw[pos]=='.'
                                 || raw[pos]=='e' || raw[pos]=='E' || raw[pos]=='+' || raw[pos]=='-')) ++pos;
        require(pos>start);
        const std::string token=raw.substr(start,pos-start);
        char* end=nullptr;
        // strtod is correctly rounded, which is what the interpreter's float() gives.
        const double value=std::strtod(token.c_str(),&end);
        require(end!=nullptr && *end=='\0' && std::isfinite(value));
        return value;
    }
    Value value(std::size_t depth) {
        node(depth);
        space();
        require(pos<raw.size());
        Value result;
        const char c=raw[pos];
        if(c=='{') {
            ++pos;
            Value::Object members;
            space();
            if(!take('}')) {
                while(true) {
                    space();
                    const std::string key=string_value();
                    space();expect(':');
                    require(members.emplace(key,value(depth+1)).second);
                    space();
                    if(take('}')) break;
                    expect(',');
                }
            }
            result.data=std::move(members);
        } else if(c=='[') {
            ++pos;
            Value::Array items;
            space();
            if(!take(']')) {
                while(true) {
                    items.push_back(value(depth+1));
                    space();
                    if(take(']')) break;
                    expect(',');
                }
            }
            result.data=std::move(items);
        } else if(c=='"') {
            result.data=string_value();
        } else if(raw.compare(pos,4,"true")==0) {pos+=4;result.data=true;}
        else if(raw.compare(pos,5,"false")==0) {pos+=5;result.data=false;}
        else if(raw.compare(pos,4,"null")==0) {pos+=4;result.data=nullptr;}
        else result.data=number_value();
        return result;
    }
};
}
Value parse(const std::string& bytes) {
    require(bytes.size()<=max_bytes);
    Reader reader{bytes};
    Value result=reader.value(0);
    reader.space();
    require(reader.pos==bytes.size());
    return result;
}
const Value::Object& object(const Value& value) {
    const auto* found=std::get_if<Value::Object>(&value.data);
    require(found!=nullptr);
    return *found;
}
const Value::Array& array(const Value& value) {
    const auto* found=std::get_if<Value::Array>(&value.data);
    require(found!=nullptr);
    return *found;
}
const std::string& text(const Value& value) {
    const auto* found=std::get_if<std::string>(&value.data);
    require(found!=nullptr);
    return *found;
}
double number(const Value& value) {
    const auto* found=std::get_if<double>(&value.data);
    require(found!=nullptr);
    return *found;
}
bool boolean(const Value& value) {
    const auto* found=std::get_if<bool>(&value.data);
    require(found!=nullptr);
    return *found;
}
bool is_null(const Value& value) {return std::holds_alternative<std::nullptr_t>(value.data);}
bool has(const Value& value,const std::string& key) {return object(value).count(key)==1;}
const Value& field(const Value& value,const std::string& key) {
    const auto& members=object(value);
    const auto found=members.find(key);
    require(found!=members.end());
    return found->second;
}
double number_or(const Value& value,const std::string& key,double fallback) {
    const auto& members=object(value);
    const auto found=members.find(key);
    return found==members.end() ? fallback : number(found->second);
}
}
