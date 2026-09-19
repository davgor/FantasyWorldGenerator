#include "cityshapes.hpp"
#include "globe.hpp"
#include "numeric.hpp"
#include <algorithm>
#include <cerrno>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <set>
namespace fantasy_world_generator::cityshapes {
namespace {
// ---------------------------------------------------------------------------
// A JSON model that keeps int and float apart.
//
// Core's catalogue reader collapses every number to a double, which is fine for
// arithmetic and fatal here: the catalogue's identity is the sha256 of Python's
// `json.dumps` of the parsed document, and Python writes `12000` for an int and
// `1000000000000.0` for a float. Lose the distinction and every seeded draw in the
// planner moves, so the port carries its own reader.
// ---------------------------------------------------------------------------
struct Node {
    enum class Kind {Null,Bool,Int,Float,String,Array,Object};
    Kind kind=Kind::Null;
    bool boolean=false;
    double number=0.;
    std::int64_t whole=0;
    bool whole_fits=false;
    // String payload, or the integer literal when the value does not fit an int64.
    std::string text;
    std::vector<Node> items;
    std::map<std::string,Node> fields;
};
[[noreturn]] void malformed(const std::string& detail) {
    throw ShapeError("Malformed city-shape catalogue: "+detail);
}
// `data['key']` on a dict: a missing key is a KeyError, which validate_catalogue
// re-raises as a malformed catalogue with `str(exc)`, and str(KeyError('k')) is "'k'".
const Node& at(const Node& node,const std::string& key) {
    if(node.kind!=Node::Kind::Object) malformed("not a mapping");
    const auto found=node.fields.find(key);
    if(found==node.fields.end()) malformed("'"+key+"'");
    return found->second;
}
bool has(const Node& node,const std::string& key) {
    return node.kind==Node::Kind::Object && node.fields.count(key)!=0;
}
const std::string& text_of(const Node& node) {
    if(node.kind!=Node::Kind::String) malformed("expected a string");
    return node.text;
}
// `_number(value)`: `type(value) in (int, float) and math.isfinite(value)`. A bool is
// not a number here, because `type(True)` is `bool`, not `int`.
bool is_number(const Node& node) {
    return (node.kind==Node::Kind::Int||node.kind==Node::Kind::Float) && std::isfinite(node.number);
}
bool is_truthy(const Node& node) {
    switch(node.kind) {
        case Node::Kind::Null: return false;
        case Node::Kind::Bool: return node.boolean;
        case Node::Kind::Int: case Node::Kind::Float: return node.number!=0.;
        case Node::Kind::String: return !node.text.empty();
        case Node::Kind::Array: return !node.items.empty();
        case Node::Kind::Object: return !node.fields.empty();
    }
    return false;
}
// ---------------------------------------------------------------------------
// Reader. Strict JSON plus the NaN/Infinity literals CPython's json accepts, and the
// `_unique` object_pairs_hook, which makes a repeated key a fault rather than a merge.
// ---------------------------------------------------------------------------
struct Reader {
    const std::string& raw;
    std::size_t pos=0,depth=0;
    [[noreturn]] void fail() const {throw ShapeError("Invalid city-shape JSON");}
    void space() {
        while(pos<raw.size() && (raw[pos]==' '||raw[pos]=='\t'||raw[pos]=='\r'||raw[pos]=='\n')) ++pos;
    }
    bool take(char c) {if(pos<raw.size() && raw[pos]==c) {++pos;return true;} return false;}
    void expect(char c) {if(!take(c)) fail();}
    bool literal(const char* word) {
        const std::size_t length=std::strlen(word);
        if(raw.compare(pos,length,word)!=0) return false;
        pos+=length;
        return true;
    }
    unsigned hex_quad() {
        if(pos+4>raw.size()) fail();
        unsigned code=0;
        for(int i=0;i<4;++i) {
            const char digit=raw[pos++];
            code<<=4;
            if(digit>='0'&&digit<='9') code|=static_cast<unsigned>(digit-'0');
            else if(digit>='a'&&digit<='f') code|=static_cast<unsigned>(digit-'a'+10);
            else if(digit>='A'&&digit<='F') code|=static_cast<unsigned>(digit-'A'+10);
            else fail();
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
        out+=static_cast<char>(0xF0|(code>>18));
        out+=static_cast<char>(0x80|((code>>12)&0x3F));
        out+=static_cast<char>(0x80|((code>>6)&0x3F));
        out+=static_cast<char>(0x80|(code&0x3F));
    }
    std::string string_value() {
        expect('"');
        std::string out;
        while(true) {
            if(pos>=raw.size()) fail();
            const char c=raw[pos++];
            if(c=='"') break;
            if(c!='\\') {out+=c;continue;}
            if(pos>=raw.size()) fail();
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
                    unsigned code=hex_quad();
                    if(code>=0xD800 && code<=0xDBFF && pos+2<=raw.size()
                       && raw[pos]=='\\' && raw[pos+1]=='u') {
                        const std::size_t mark=pos;
                        pos+=2;
                        const unsigned low=hex_quad();
                        if(low>=0xDC00 && low<=0xDFFF) code=0x10000+((code-0xD800)<<10)+(low-0xDC00);
                        else pos=mark;
                    }
                    append_utf8(out,code);
                    break;
                }
                default: fail();
            }
        }
        return out;
    }
    Node number_value() {
        const std::size_t start=pos;
        bool real=false;
        if(pos<raw.size() && raw[pos]=='-') ++pos;
        if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
        while(pos<raw.size() && raw[pos]>='0' && raw[pos]<='9') ++pos;
        if(pos<raw.size() && raw[pos]=='.') {
            real=true;++pos;
            if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
            while(pos<raw.size() && raw[pos]>='0' && raw[pos]<='9') ++pos;
        }
        if(pos<raw.size() && (raw[pos]=='e'||raw[pos]=='E')) {
            real=true;++pos;
            if(pos<raw.size() && (raw[pos]=='+'||raw[pos]=='-')) ++pos;
            if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
            while(pos<raw.size() && raw[pos]>='0' && raw[pos]<='9') ++pos;
        }
        const std::string token=raw.substr(start,pos-start);
        Node node;
        node.number=std::strtod(token.c_str(),nullptr);
        if(real) {node.kind=Node::Kind::Float;return node;}
        node.kind=Node::Kind::Int;
        errno=0;
        char* end=nullptr;
        const long long parsed=std::strtoll(token.c_str(),&end,10);
        if(errno==0 && end!=nullptr && *end=='\0') {
            node.whole=static_cast<std::int64_t>(parsed);
            node.whole_fits=true;
            // str(int) and the JSON literal agree except for "-0", which Python
            // renders as "0".
            node.text=std::to_string(node.whole);
        } else {
            node.text=token;
        }
        return node;
    }
    Node value() {
        if(++depth>200) fail();
        space();
        if(pos>=raw.size()) fail();
        Node node;
        const char c=raw[pos];
        if(c=='{') {
            ++pos;
            node.kind=Node::Kind::Object;
            space();
            if(!take('}')) {
                while(true) {
                    space();
                    const std::string key=string_value();
                    space();expect(':');
                    Node child=value();
                    // `_unique`: a repeated key is rejected, never merged.
                    if(!node.fields.emplace(key,std::move(child)).second)
                        throw ShapeError("Duplicate city-shape JSON key");
                    space();
                    if(take('}')) break;
                    expect(',');
                }
            }
        } else if(c=='[') {
            ++pos;
            node.kind=Node::Kind::Array;
            space();
            if(!take(']')) {
                while(true) {
                    node.items.push_back(value());
                    space();
                    if(take(']')) break;
                    expect(',');
                }
            }
        } else if(c=='"') {
            node.kind=Node::Kind::String;
            node.text=string_value();
        } else if(literal("true")) {node.kind=Node::Kind::Bool;node.boolean=true;}
        else if(literal("false")) {node.kind=Node::Kind::Bool;node.boolean=false;}
        else if(literal("null")) {node.kind=Node::Kind::Null;}
        else if(literal("NaN")) {
            node.kind=Node::Kind::Float;node.number=std::numeric_limits<double>::quiet_NaN();
        } else if(literal("Infinity")) {
            node.kind=Node::Kind::Float;node.number=std::numeric_limits<double>::infinity();
        } else if(literal("-Infinity")) {
            node.kind=Node::Kind::Float;node.number=-std::numeric_limits<double>::infinity();
        } else node=number_value();
        --depth;
        return node;
    }
};
Node load_json(const std::string& bytes) {
    Reader reader{bytes};
    Node root=reader.value();
    reader.space();
    if(reader.pos!=bytes.size()) reader.fail();
    return root;
}
// ---------------------------------------------------------------------------
// Python's repr of a float, which is what json.dumps writes.
//
// Not "%.17g": repr is the shortest decimal that reads back to the same double, and
// it switches to exponent form on its own rule (decpt <= -4 or decpt > 16), not on
// %g's. `1000000000000.0` and `1e+16` both appear in this catalogue's neighbourhood.
// ---------------------------------------------------------------------------
std::string py_repr(double value) {
    if(std::isnan(value)) return "NaN";
    if(std::isinf(value)) return value>0.?"Infinity":"-Infinity";
    if(value==0.) return std::signbit(value)?"-0.0":"0.0";
    char buffer[64];
    int precision=1;
    for(;precision<17;++precision) {
        std::snprintf(buffer,sizeof buffer,"%.*e",precision-1,value);
        if(std::strtod(buffer,nullptr)==value) break;
    }
    if(precision>=17) std::snprintf(buffer,sizeof buffer,"%.16e",value);
    // buffer is [-]d[.ddd]e[+-]dd; split it into the digit string and the exponent.
    const char* cursor=buffer;
    std::string sign;
    if(*cursor=='-') {sign="-";++cursor;}
    std::string digits;
    for(;*cursor && *cursor!='e' && *cursor!='E';++cursor) if(*cursor!='.') digits+=*cursor;
    const int exponent=(*cursor)?std::atoi(cursor+1):0;
    // The minimal round-tripping precision never leaves a trailing zero, but a guard
    // costs nothing and keeps the digit string canonical.
    while(digits.size()>1 && digits.back()=='0') digits.pop_back();
    const int decpt=exponent+1;
    std::string out=sign;
    if(decpt<=-4 || decpt>16) {
        out+=digits[0];
        if(digits.size()>1) {out+='.';out.append(digits,1,std::string::npos);}
        const int e=decpt-1;
        out+='e';
        out+=(e<0?'-':'+');
        const int magnitude=e<0?-e:e;
        char tail[16];
        std::snprintf(tail,sizeof tail,"%02d",magnitude);
        out+=tail;
        return out;
    }
    if(decpt<=0) {
        out+="0.";
        out.append(static_cast<std::size_t>(-decpt),'0');
        out+=digits;
        return out;
    }
    if(static_cast<std::size_t>(decpt)>=digits.size()) {
        out+=digits;
        out.append(static_cast<std::size_t>(decpt)-digits.size(),'0');
        out+=".0";
        return out;
    }
    out.append(digits,0,static_cast<std::size_t>(decpt));
    out+='.';
    out.append(digits,static_cast<std::size_t>(decpt),std::string::npos);
    return out;
}
// json.dumps with the default ensure_ascii: printable ASCII passes through, everything
// else becomes \uXXXX, astral code points as a surrogate pair.
void escape(const std::string& value,std::string& out) {
    out+='"';
    std::size_t index=0;
    while(index<value.size()) {
        const unsigned char lead=static_cast<unsigned char>(value[index]);
        unsigned code=lead;
        std::size_t width=1;
        if(lead>=0xF0) {code=lead&0x07u;width=4;}
        else if(lead>=0xE0) {code=lead&0x0Fu;width=3;}
        else if(lead>=0xC0) {code=lead&0x1Fu;width=2;}
        if(width>1) {
            if(index+width>value.size()) width=1,code=lead;
            else {
                for(std::size_t k=1;k<width;++k) {
                    const unsigned char next=static_cast<unsigned char>(value[index+k]);
                    if((next&0xC0u)!=0x80u) {width=1;code=lead;break;}
                    code=(code<<6)|(next&0x3Fu);
                }
            }
        }
        index+=width;
        switch(code) {
            case '\\': out+="\\\\";continue;
            case '"': out+="\\\"";continue;
            case '\b': out+="\\b";continue;
            case '\f': out+="\\f";continue;
            case '\n': out+="\\n";continue;
            case '\r': out+="\\r";continue;
            case '\t': out+="\\t";continue;
            default: break;
        }
        if(code>=0x20 && code<=0x7E) {out+=static_cast<char>(code);continue;}
        char unit[8];
        if(code<0x10000) {
            std::snprintf(unit,sizeof unit,"\\u%04x",code);
            out+=unit;
        } else {
            const unsigned rest=code-0x10000u;
            std::snprintf(unit,sizeof unit,"\\u%04x",0xD800u|((rest>>10)&0x3FFu));
            out+=unit;
            std::snprintf(unit,sizeof unit,"\\u%04x",0xDC00u|(rest&0x3FFu));
            out+=unit;
        }
    }
    out+='"';
}
// json.dumps(node, sort_keys=True, separators=(',',':')). std::map already iterates in
// byte order, which is code-point order for UTF-8 keys, which is Python's str order.
void dump(const Node& node,std::string& out) {
    switch(node.kind) {
        case Node::Kind::Null: out+="null";return;
        case Node::Kind::Bool: out+=node.boolean?"true":"false";return;
        case Node::Kind::Int: out+=node.text;return;
        case Node::Kind::Float: out+=py_repr(node.number);return;
        case Node::Kind::String: escape(node.text,out);return;
        case Node::Kind::Array: {
            out+='[';
            for(std::size_t i=0;i<node.items.size();++i) {
                if(i) out+=',';
                dump(node.items[i],out);
            }
            out+=']';
            return;
        }
        case Node::Kind::Object: {
            out+='{';
            bool first=true;
            for(const auto& entry:node.fields) {
                if(!first) out+=',';
                first=false;
                escape(entry.first,out);
                out+=':';
                dump(entry.second,out);
            }
            out+='}';
            return;
        }
    }
}
// ---------------------------------------------------------------------------
// CPython's builtin sum(): exact integer accumulation until the first float, then
// Neumaier compensation from that partial. A plain += loop over the candidate weights
// differs by an ulp, which is enough to pick a different city shape.
// ---------------------------------------------------------------------------
class PySum {
  public:
    void add_int(std::int64_t value) {
        if(integer_) {whole_+=value;return;}
        floats_.add(static_cast<double>(value));
    }
    void add_float(double value) {
        if(integer_) {
            // `PyNumber_Add(int_so_far, item)` starts the float loop, and its
            // compensation starts at zero.
            integer_=false;
            floats_.total=static_cast<double>(whole_)+value;
            floats_.compensation=0.;
            return;
        }
        floats_.add(value);
    }
    bool is_integer() const {return integer_;}
    std::int64_t integer() const {return whole_;}
    double real() const {return integer_?static_cast<double>(whole_):floats_.value();}
  private:
    bool integer_=true;
    std::int64_t whole_=0;
    Sum floats_;
};
// ---------------------------------------------------------------------------
// Python's round(x, 6).
//
// Banker's rounding on the *decimal* expansion, not on the binary value: CPython
// formats x to six places with _Py_dg_dtoa and reads the string back. "%.6f" is the
// same correctly rounded conversion, except that an exact tie leans on the C library's
// tie rule, so ties are settled here instead. A tie at six decimals needs x*10^6 to be
// exactly k+.5, which forces x = m/128 with m odd and nothing else.
// ---------------------------------------------------------------------------
double python_round6(double x) {
    if(!std::isfinite(x)) return x;
    if(std::fabs(x)<4.0e9) {
        const double scaled=x*128.;
        if(scaled==std::floor(scaled) && std::fabs(std::fmod(scaled,2.))==1.) {
            // x*10^6 = (m*15625)/2 with m*15625 odd, so the two neighbours straddle a
            // half and the even one wins. Both stay far inside 2^53.
            const std::int64_t odd=static_cast<std::int64_t>(scaled)*15625;
            const std::int64_t low=(odd-1)/2,high=low+1;
            const std::int64_t chosen=(low%2==0)?low:high;
            return static_cast<double>(chosen)/1000000.;
        }
    }
    char buffer[512];
    std::snprintf(buffer,sizeof buffer,"%.6f",x);
    return std::strtod(buffer,nullptr);
}
std::size_t code_points(const std::string& value) {
    std::size_t count=0;
    for(char c:value) if((static_cast<unsigned char>(c)&0xC0u)!=0x80u) ++count;
    return count;
}
// ---------------------------------------------------------------------------
// validate_catalogue
// ---------------------------------------------------------------------------
void check_rule(const Node& rule,const Node& features) {
    if(rule.kind!=Node::Kind::Object || !has(rule,"field")
       || rule.fields.at("field").kind!=Node::Kind::String
       || !has(features,rule.fields.at("field").text))
        throw ShapeError("Unknown shape-rule field");
    for(const auto& entry:rule.fields)
        if(entry.first!="field" && entry.first!="min" && entry.first!="max" && entry.first!="equals")
            throw ShapeError("Invalid shape rule");
    if(rule.fields.size()<2) throw ShapeError("Invalid shape rule");
    const Node& definition=at(features,rule.fields.at("field").text);
    const bool boolean=at(definition,"type").kind==Node::Kind::String
                       && at(definition,"type").text=="boolean";
    if(boolean) {
        if(rule.fields.size()!=2 || !has(rule,"equals")
           || rule.fields.at("equals").kind!=Node::Kind::Bool)
            throw ShapeError("Boolean rule requires explicit boolean equality");
        return;
    }
    for(const auto& entry:rule.fields)
        if(entry.first!="field" && !is_number(entry.second))
            throw ShapeError("Nonfinite shape-rule value");
    const double low=has(rule,"min")?rule.fields.at("min").number:-std::numeric_limits<double>::infinity();
    const double high=has(rule,"max")?rule.fields.at("max").number:std::numeric_limits<double>::infinity();
    if(low>high) throw ShapeError("Reversed shape-rule range");
}
void validate_catalogue(const Node& data) {
    if(at(data,"schema").kind!=Node::Kind::String
       || at(data,"schema").text!="fantasy-world-generator.city-shapes"
       || at(data,"schema_version").kind!=Node::Kind::Int
       || at(data,"schema_version").whole!=1)
        throw ShapeError("Unsupported city-shape schema");
    if(at(data,"revision").kind!=Node::Kind::Int || at(data,"revision").whole<1)
        throw ShapeError("Invalid city-shape revision");
    const Node& features=at(data,"site_features");
    if(features.kind!=Node::Kind::Object) malformed("not a mapping");
    // The reference walks `features.values()` in insertion order; a map walks them
    // sorted. Both accept and reject the same catalogues -- only which fault a broken
    // one reports first can differ.
    for(const auto& entry:features.fields) {
        const Node& definition=entry.second;
        const Node& type=at(definition,"type");
        const bool named=type.kind==Node::Kind::String && (type.text=="boolean"||type.text=="number");
        if(!named) throw ShapeError("Invalid feature type");
        if(type.text=="number") {
            const Node& low=at(definition,"min");
            const Node& high=at(definition,"max");
            if(!is_number(low) || !is_number(high) || low.number>high.number)
                throw ShapeError("Invalid feature range");
        }
    }
    const Node& selection=at(data,"selection");
    const Node& algorithm=at(selection,"algorithm");
    if(algorithm.kind!=Node::Kind::String || algorithm.text!="sha256_weighted_v1")
        throw ShapeError("Unsupported selection algorithm");
    const Node& required=at(selection,"required_site_fields");
    if(required.kind!=Node::Kind::Array || required.items.empty())
        throw ShapeError("Unknown required feature");
    for(const Node& name:required.items)
        if(name.kind!=Node::Kind::String || !has(features,name.text))
            throw ShapeError("Unknown required feature");
    const Node& penalty=at(selection,"repetition_penalty");
    if(!is_number(penalty) || penalty.number<0.) throw ShapeError("Invalid repetition penalty");
    const Node& sources=at(data,"sources");
    if(sources.kind!=Node::Kind::Object) malformed("not a mapping");
    for(const auto& entry:sources.fields) {
        const Node& url=at(entry.second,"url");
        if(url.kind!=Node::Kind::String) malformed("expected a string");
        if(url.text.rfind("https://",0)!=0) throw ShapeError("Missing research attribution");
        if(!is_truthy(at(entry.second,"supports")))
            throw ShapeError("Missing research attribution");
    }
    const Node& shapes=at(data,"shapes");
    if(shapes.kind!=Node::Kind::Array) malformed("not a sequence");
    if(shapes.items.empty()) throw ShapeError("Empty shape catalogue");
    std::set<std::string> seen;
    for(const Node& shape:shapes.items) {
        const Node& id=at(shape,"id");
        if(id.kind!=Node::Kind::String || id.text.empty() || seen.count(id.text)!=0)
            throw ShapeError("Duplicate or invalid shape ID");
        seen.insert(id.text);
        if(at(shape,"enabled_by_default").kind!=Node::Kind::Bool)
            throw ShapeError("Invalid default flag");
        const Node& classes=at(shape,"city_classes");
        if(classes.kind!=Node::Kind::Array || classes.items.empty())
            throw ShapeError("Invalid city class");
        for(const Node& name:classes.items)
            if(name.kind!=Node::Kind::String
               || (name.text!="small" && name.text!="medium" && name.text!="capital"))
                throw ShapeError("Invalid city class");
        const Node& base=at(shape,"base_weight");
        if(!is_number(base) || !(base.number>0. && base.number<=1000.))
            throw ShapeError("Invalid shape weight");
        const Node& source_ids=at(at(shape,"history"),"source_ids");
        if(source_ids.kind!=Node::Kind::Array || source_ids.items.empty())
            throw ShapeError("Unknown historical source");
        for(const Node& name:source_ids.items)
            if(name.kind!=Node::Kind::String || !has(sources,name.text))
                throw ShapeError("Unknown historical source");
        const Node& eligibility=at(shape,"eligibility");
        if(eligibility.kind!=Node::Kind::Object || eligibility.fields.size()!=1
           || !has(eligibility,"all"))
            throw ShapeError("Invalid eligibility expression");
        const Node& rules=at(eligibility,"all");
        if(rules.kind!=Node::Kind::Array) malformed("not a sequence");
        for(const Node& rule:rules.items) check_rule(rule,features);
        const Node& preferences=at(shape,"preferences");
        if(preferences.kind!=Node::Kind::Array) malformed("not a sequence");
        for(const Node& preference:preferences.items) {
            check_rule(at(preference,"when"),features);
            const Node& bonus=at(preference,"bonus");
            if(!is_number(bonus) || !(bonus.number>=0. && bonus.number<=1000.))
                throw ShapeError("Invalid preference weight");
        }
        const Node& variation=at(shape,"variation");
        if(variation.kind!=Node::Kind::Object) malformed("not a mapping");
        for(const auto& entry:variation.fields) {
            const Node& parameter=entry.second;
            const Node& low=at(parameter,"min");
            const Node& high=at(parameter,"max");
            if(!is_number(low) || !is_number(high) || low.number>high.number)
                throw ShapeError("Invalid variation range");
            const bool flagged=has(parameter,"integer");
            if(flagged && parameter.fields.at("integer").kind!=Node::Kind::Bool)
                throw ShapeError("Invalid integer flag");
            if(flagged && parameter.fields.at("integer").boolean
               && (low.kind!=Node::Kind::Int || high.kind!=Node::Kind::Int))
                throw ShapeError("Integer variation needs integer endpoints");
        }
    }
}
// ---------------------------------------------------------------------------
// Ranking
// ---------------------------------------------------------------------------
const SiteValue* lookup(const Site& site,const std::string& key) {
    for(const auto& entry:site) if(entry.first==key) return &entry.second;
    return nullptr;
}
double as_double(const SiteValue& value) {
    return value.is_boolean?(value.boolean?1.:0.):value.number;
}
bool equal_to(const SiteValue& value,const Node& other) {
    if(value.is_boolean && other.kind==Node::Kind::Bool) return value.boolean==other.boolean;
    if(other.kind==Node::Kind::Bool) return value.number==(other.boolean?1.:0.);
    return as_double(value)==other.number;
}
// `_matches`. The comparisons run in double; the reference compares a Python int to a
// float exactly, which only diverges past 2^53, far outside any site feature's range.
bool matches(const Node& rule,const Site& site) {
    const std::string& field=at(rule,"field").text;
    const SiteValue* value=lookup(site,field);
    if(value==nullptr) return false;
    if(has(rule,"equals") && !equal_to(*value,rule.fields.at("equals"))) return false;
    if(has(rule,"min") && !(as_double(*value)>=rule.fields.at("min").number)) return false;
    if(has(rule,"max") && !(as_double(*value)<=rule.fields.at("max").number)) return false;
    return true;
}
std::string sha256_hex(const std::string& payload) {return sha256(payload);}
std::uint64_t leading_word(const std::string& hex) {
    std::uint64_t word=0;
    for(int i=0;i<16;++i) {
        const char digit=hex[static_cast<std::size_t>(i)];
        unsigned value=0;
        if(digit>='0'&&digit<='9') value=static_cast<unsigned>(digit-'0');
        else value=static_cast<unsigned>(digit-'a'+10);
        word=(word<<4)|value;
    }
    return word;
}
std::string& mutable_path() {
    static std::string path="Sim/icarus_sim/city_shapes.json";
    return path;
}
}
struct Catalogue::Document {
    Node root;
    std::string canonical;
    std::string identity;
    std::map<std::string,std::size_t> index;   // shape id -> position in data['shapes']
};
Catalogue Catalogue::parse(const std::string& bytes) {
    auto document=std::make_shared<Document>();
    document->root=load_json(bytes);
    validate_catalogue(document->root);
    dump(document->root,document->canonical);
    document->identity=sha256_hex(document->canonical);
    const Node& shapes=at(document->root,"shapes");
    for(std::size_t i=0;i<shapes.items.size();++i)
        document->index.emplace(at(shapes.items[i],"id").text,i);
    Catalogue result;
    result.document_=document;
    return result;
}
Catalogue Catalogue::read(const std::string& path) {
    std::ifstream stream(path,std::ios::binary);
    if(!stream) throw ShapeError("Missing city-shape catalogue: "+path);
    std::string bytes((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());
    return parse(bytes);
}
std::int64_t Catalogue::revision() const {return at(document_->root,"revision").whole;}
const std::string& Catalogue::identity() const {return document_->identity;}
const std::string& Catalogue::canonical_json() const {return document_->canonical;}
const std::string& Catalogue::family(const std::string& shape_id) const {
    const auto found=document_->index.find(shape_id);
    if(found==document_->index.end()) throw ShapeError("Unknown city shape: "+shape_id);
    return at(at(document_->root,"shapes").items[found->second],"family").text;
}
std::vector<std::string> Catalogue::shape_ids() const {
    std::vector<std::string> ids;
    for(const Node& shape:at(document_->root,"shapes").items) ids.push_back(at(shape,"id").text);
    return ids;
}
std::vector<Candidate> Catalogue::rank(const Site& site,const std::string& city_class,
                                       const std::map<std::string,std::int64_t>& nearby_counts,
                                       bool include_later) const {
    const Node& data=document_->root;
    const Node& selection=at(data,"selection");
    const Node& features=at(data,"site_features");
    for(const Node& name:at(selection,"required_site_fields").items)
        if(lookup(site,name.text)==nullptr)
            throw ShapeError("Missing required footprint location data");
    if(city_class!="small" && city_class!="medium" && city_class!="capital")
        throw ShapeError("Invalid city class or period option");
    // Insertion order, so a site with several faults reports the one the reference
    // reports.
    for(const auto& entry:site) {
        if(!has(features,entry.first))
            throw ShapeError("Unknown site feature: "+entry.first);
        const Node& definition=at(features,entry.first);
        if(at(definition,"type").text=="boolean") {
            if(!entry.second.is_boolean) throw ShapeError("Expected boolean site feature");
        } else if(entry.second.is_boolean || !std::isfinite(entry.second.number)
                  || !(at(definition,"min").number<=entry.second.number
                       && entry.second.number<=at(definition,"max").number))
            throw ShapeError("Out-of-range site feature");
    }
    const Node& shapes=at(data,"shapes");
    std::set<std::string> ids;
    for(const Node& shape:shapes.items) ids.insert(at(shape,"id").text);
    for(const auto& entry:nearby_counts)
        if(ids.count(entry.first)==0 || !(entry.second>=0 && entry.second<=10000))
            throw ShapeError("Invalid nearby shape counts");
    // `sorted(data['shapes'], key=lambda s: s['id'])`; IDs are unique, so the sort is
    // total and stability cannot be observed.
    std::vector<const Node*> ordered;
    ordered.reserve(shapes.items.size());
    for(const Node& shape:shapes.items) ordered.push_back(&shape);
    std::stable_sort(ordered.begin(),ordered.end(),[](const Node* a,const Node* b) {
        return at(*a,"id").text<at(*b,"id").text;
    });
    const Node& penalty=at(selection,"repetition_penalty");
    std::vector<Candidate> ranked;
    for(const Node* entry:ordered) {
        const Node& shape=*entry;
        if(!at(shape,"enabled_by_default").boolean && !include_later) continue;
        bool classed=false;
        for(const Node& name:at(shape,"city_classes").items) if(name.text==city_class) classed=true;
        if(!classed) continue;
        bool eligible=true;
        for(const Node& rule:at(at(shape,"eligibility"),"all").items)
            if(!matches(rule,site)) {eligible=false;break;}
        if(!eligible) continue;
        std::vector<const Node*> matched;
        for(const Node& preference:at(shape,"preferences").items)
            if(matches(at(preference,"when"),site)) matched.push_back(&preference);
        // Every bonus in the shipped catalogue is a JSON integer, so this sum takes
        // CPython's exact integer path; PySum switches to Neumaier the moment one of
        // them is written with a decimal point.
        PySum bonuses;
        for(const Node* preference:matched) {
            const Node& bonus=at(*preference,"bonus");
            if(bonus.kind==Node::Kind::Int && bonus.whole_fits) bonuses.add_int(bonus.whole);
            else bonuses.add_float(bonus.number);
        }
        const Node& base=at(shape,"base_weight");
        const std::string& id=at(shape,"id").text;
        double numerator;
        if(base.kind==Node::Kind::Int && base.whole_fits && bonuses.is_integer())
            numerator=static_cast<double>(base.whole+bonuses.integer());
        else numerator=base.number+bonuses.real();
        const auto counted=nearby_counts.find(id);
        const std::int64_t count=counted==nearby_counts.end()?0:counted->second;
        double denominator;
        if(penalty.kind==Node::Kind::Int && penalty.whole_fits)
            denominator=static_cast<double>(1+count*penalty.whole);
        else denominator=1.+static_cast<double>(count)*penalty.number;
        Candidate candidate;
        candidate.id=id;
        candidate.family=at(shape,"family").text;
        candidate.weight=numerator/denominator;
        for(const Node* preference:matched)
            candidate.matched_preferences.push_back(at(at(*preference,"when"),"field").text);
        ranked.push_back(std::move(candidate));
    }
    return ranked;
}
Selection Catalogue::select_shape(const Site& site,std::int64_t seed,const std::string& city_id,
                                  const std::string& city_class,
                                  const std::map<std::string,std::int64_t>& nearby_counts,
                                  bool include_later) const {
    const std::size_t length=code_points(city_id);
    if(length<1 || length>256)
        throw ShapeError("Expected an integer seed and stable nonempty city ID");
    const Node& data=document_->root;
    const std::string& identity_hex=document_->identity;
    Selection result;
    result.version=1;
    result.catalogue_revision=revision();
    result.catalogue_sha256=identity_hex;
    result.candidates=rank(site,city_class,nearby_counts,include_later);
    if(result.candidates.empty()) {
        result.reason="No compatible shape; change site or provide missing location facts.";
        return result;
    }
    const auto unit=[&](const std::string& label) {
        std::string payload="[";
        payload+=std::to_string(seed);
        payload+=',';escape(city_id,payload);
        payload+=',';escape(identity_hex,payload);
        payload+=',';escape(label,payload);
        payload+=']';
        // int.from_bytes(digest[:8], 'big') / 2**64. Dividing by a power of two is
        // exact, so the double cast of the word is the whole of the rounding, which is
        // what Python's correctly rounded int/int does too.
        return static_cast<double>(leading_word(sha256_hex(payload)))/18446744073709551616.;
    };
    // The one sum() that decides which city gets built: floats, so Neumaier.
    PySum total;
    for(const Candidate& row:result.candidates) total.add_float(row.weight);
    double target=unit("shape")*total.real();
    const Candidate* chosen=&result.candidates.back();
    for(const Candidate& row:result.candidates) {
        target-=row.weight;
        if(target<0.) {chosen=&row;break;}
    }
    const Node& shape=at(data,"shapes").items[document_->index.at(chosen->id)];
    const Node& variation=at(shape,"variation");
    for(const auto& entry:variation.fields) {
        const Node& interval=entry.second;
        const Node& low=at(interval,"min");
        const Node& high=at(interval,"max");
        const double u=unit(at(shape,"id").text+":"+entry.first);
        Parameter parameter;
        if(has(interval,"integer") && interval.fields.at("integer").boolean) {
            // Validated to have integer endpoints, so the span is exact integer
            // arithmetic in the reference and in an int64 here.
            const std::int64_t span=high.whole-low.whole+1;
            const std::int64_t step=static_cast<std::int64_t>(u*static_cast<double>(span));
            parameter.integer=true;
            parameter.whole=std::min(high.whole,low.whole+step);
        } else {
            parameter.real=python_round6(low.number+u*(high.number-low.number));
        }
        result.parameters.emplace(entry.first,parameter);
    }
    result.has_shape=true;
    result.shape_id=at(shape,"id").text;
    const Node& layout=at(shape,"layout");
    for(const auto& entry:layout.fields) {
        if(entry.second.kind==Node::Kind::String) result.layout.emplace(entry.first,entry.second.text);
        else {
            std::string rendered;
            dump(entry.second,rendered);
            result.layout.emplace(entry.first,rendered);
        }
    }
    for(const Node& name:at(at(shape,"history"),"source_ids").items)
        result.source_ids.push_back(name.text);
    result.reason="Seeded weighted choice among compatible shapes.";
    return result;
}
void set_catalogue_path(const std::string& path) {mutable_path()=path;}
const std::string& catalogue_path() {return mutable_path();}
const Catalogue& load_catalogue() {
    // Keyed on path, modification time and size, as the reference's lru_cache is.
    static std::string cached_path;
    static std::uintmax_t cached_size=0;
    static std::int64_t cached_stamp=0;
    static Catalogue cached;
    static bool loaded=false;
    const std::string& path=mutable_path();
    std::error_code error;
    const std::uintmax_t size=std::filesystem::file_size(path,error);
    const auto written=std::filesystem::last_write_time(path,error);
    const std::int64_t stamp=written.time_since_epoch().count();
    if(!loaded || path!=cached_path || size!=cached_size || stamp!=cached_stamp) {
        cached=Catalogue::read(path);
        cached_path=path;
        cached_size=size;
        cached_stamp=stamp;
        loaded=true;
    }
    return cached;
}
std::vector<Candidate> rank_shapes(const Site& site,const std::string& city_class,
                                   const std::map<std::string,std::int64_t>& nearby_counts,
                                   bool include_later) {
    return load_catalogue().rank(site,city_class,nearby_counts,include_later);
}
Selection select_shape(const Site& site,std::int64_t seed,const std::string& city_id,
                       const std::string& city_class,
                       const std::map<std::string,std::int64_t>& nearby_counts,
                       bool include_later) {
    return load_catalogue().select_shape(site,seed,city_id,city_class,nearby_counts,include_later);
}
}
