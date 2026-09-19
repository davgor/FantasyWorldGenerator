#include "settlementpresets.hpp"
#include "numeric.hpp"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <map>
#include <set>
namespace fantasy_world_generator::settlementpresets {
namespace {
// ---------------------------------------------------------------------------
// Module constants, copied from the reference verbatim.
// ---------------------------------------------------------------------------
const char* const building_sections[]={"building_packs","layout_profiles","structure_blocks","housing_profiles"};
const char* const city_blocks[]={"small_city","medium_city","capital_city"};
const char* const hamlet_block="hamlet";
const char* const staff_levels[]={"minimum","target","maximum"};
const std::set<std::string>& placement_conditions() {
    static const std::set<std::string> set={
        "usable_groundwater","water_collection_or_delivery","navigable_shore",
        "flowing_water","reliable_wind","ore_and_fuel_supply","food_surplus","working_animals",
        "clay_and_fuel_supply","medicinal_supply","clear_sky_view","isolation_access",
        "route_crossing","grade_change","retention_needed","defended_perimeter",
        "farming_support","resource_support"};
    return set;
}
// terrain_profiles.FIELDS: the complete independent trait record a civilization must
// author. validate_profile lives in that module, but validate_registry calls it for
// every entity and configuration, so the rejection order only reproduces if the port
// carries it too.
const std::set<std::string>& profile_fields() {
    static const std::set<std::string> set={
        "name","description","food_temperature_ideal","minimum_founding_residents",
        "temperature_ideal","temperature_tolerance","slope_comfort","site_slope_limit",
        "work_slope_limit","road_grade_limit","water_reach","moisture_ideal","water_weight",
        "slope_weight","climate_weight","moisture_weight","resource_weight","flood_penalty",
        "magic_penalty","mutation_limit","difficult_fraction","food_temperature_tolerance",
        "food_slope_comfort","food_moisture_ideal","irrigation","food_demand",
        "land_per_city_km2","support_multiplier","college_slope_limit",
        "college_temperature_min","college_temperature_max","college_water_reach",
        "college_flood_limit","college_suitability_min","biome_preferences",
        "food_biome_multipliers","magic_biome_preferences","food_magic_biome_multipliers"};
    return set;
}
const std::set<std::int64_t>& natural_biomes() {
    static const std::set<std::int64_t> set={0,1,2,3,4,5,6,7,8,13,15,16,17};
    return set;
}
// terrain_biome_catalogue: every natural core crossed with every magical school.
const std::set<std::string>& variant_ids() {
    static const std::set<std::string> set=[]{
        static const char* const cores[]={"ocean","tundra","desert","grassland","forest",
            "exposed_rock","snow","rainforest","lake","marsh","boreal_forest","cold_tundra","land_ice"};
        static const char* const schools[]={"weave","umbral","infernal","radiant","fire","water","earth","air"};
        std::set<std::string> built;
        for(const char* core:cores) for(const char* school:schools)
            built.insert(std::string(core)+"."+school);
        return built;
    }();
    return set;
}
[[noreturn]] void value_error(const std::string& message) {throw RegistryError("ValueError",message);}
[[noreturn]] void key_error(const std::string& key) {throw RegistryError("KeyError","'"+key+"'");}

// ---------------------------------------------------------------------------
// Python scalar semantics
// ---------------------------------------------------------------------------
// `type(v) is int`. A JSON `true` is a bool, and CPython's `type(True) is int` is
// False, so half the registry's range tests reject it; the port keeps the kinds apart.
bool is_int(const Value& v) {return v.kind==Value::Kind::Int;}
bool is_float(const Value& v) {return v.kind==Value::Kind::Float;}
bool is_number(const Value& v) {return v.is_number();}
double as_double(const Value& v) {
    if(v.kind==Value::Kind::Int) return v.whole_fits?static_cast<double>(v.whole):v.number;
    if(v.kind==Value::Kind::Bool) return v.boolean?1.:0.;
    return v.number;
}
bool finite_number(const Value& v) {return is_number(v)&&std::isfinite(as_double(v));}
// `low<=value<=high` after `type(value) in (int,float)`; every bound in this registry
// is small enough that the int-to-double widening is exact.
bool within(const Value& v,double low,double high) {
    const double x=as_double(v);
    return low<=x && x<=high;
}
// Python truthiness.
bool truthy(const Value& v) {
    switch(v.kind) {
        case Value::Kind::Null: return false;
        case Value::Kind::Bool: return v.boolean;
        case Value::Kind::Int: return v.whole_fits?v.whole!=0:v.number!=0.;
        case Value::Kind::Float: return v.number!=0.;
        case Value::Kind::String: return !v.text.empty();
        case Value::Kind::Array: return !v.items.empty();
        case Value::Kind::Object: return !v.fields.empty();
    }
    return false;
}
// Python `==`. Numeric kinds compare across the int/float/bool line, which matters for
// the `plot_m` dict comparison and the building-catalogue link check.
bool py_equal(const Value& a,const Value& b) {
    const bool a_num=a.kind==Value::Kind::Int||a.kind==Value::Kind::Float||a.kind==Value::Kind::Bool;
    const bool b_num=b.kind==Value::Kind::Int||b.kind==Value::Kind::Float||b.kind==Value::Kind::Bool;
    if(a_num&&b_num) {
        if(a.kind==Value::Kind::Int&&b.kind==Value::Kind::Int&&a.whole_fits&&b.whole_fits)
            return a.whole==b.whole;
        return as_double(a)==as_double(b);
    }
    if(a.kind!=b.kind) return false;
    switch(a.kind) {
        case Value::Kind::Null: return true;
        case Value::Kind::String: return a.text==b.text;
        case Value::Kind::Array: {
            if(a.items.size()!=b.items.size()) return false;
            for(std::size_t i=0;i<a.items.size();++i) if(!py_equal(a.items[i],b.items[i])) return false;
            return true;
        }
        case Value::Kind::Object: {
            if(a.fields.size()!=b.fields.size()) return false;
            for(const auto& entry:a.fields) {
                const Value* other=b.find(entry.first);
                if(other==nullptr||!py_equal(entry.second,*other)) return false;
            }
            return true;
        }
        default: return false;
    }
}
// `set(mapping)`: the key set, which the reference compares against a literal set in a
// dozen places. A non-mapping has no keys here; every caller short-circuits on the
// resulting inequality before it would have subscripted the value.
std::set<std::string> key_set(const Value& v) {
    std::set<std::string> keys;
    if(v.kind==Value::Kind::Object) for(const auto& entry:v.fields) keys.insert(entry.first);
    return keys;
}
// `set(sequence_of_strings)`; a non-string element can never match a member of the
// literal sets this registry tests against, so it is reported as an unmatchable slot.
bool string_set_subset(const Value& list,const std::set<std::string>& universe) {
    for(const Value& item:list.items) {
        if(!item.is_string()) return false;
        if(universe.count(item.text)==0) return false;
    }
    return true;
}
// `re.fullmatch('[a-z][a-z0-9_]*', key)`.
bool lower_identifier(const std::string& text) {
    if(text.empty()) return false;
    if(text[0]<'a'||text[0]>'z') return false;
    for(std::size_t i=1;i<text.size();++i) {
        const char c=text[i];
        if(!((c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='_')) return false;
    }
    return true;
}
// `re.fullmatch(r'building\.[a-z][a-z0-9_]*', sid)`.
bool building_identifier(const std::string& text) {
    static const std::string prefix="building.";
    if(text.compare(0,prefix.size(),prefix)!=0) return false;
    return lower_identifier(text.substr(prefix.size()));
}
// `str.strip()` with no argument strips every code point whose `isspace()` is true.
bool unicode_space(unsigned code) {
    if(code<=0x20) return (code>=0x09&&code<=0x0D)||(code>=0x1C&&code<=0x1F)||code==0x20;
    switch(code) {
        case 0x85: case 0xA0: case 0x1680: case 0x2028: case 0x2029:
        case 0x202F: case 0x205F: case 0x3000: return true;
        default: return code>=0x2000&&code<=0x200A;
    }
}
// Decode one UTF-8 code point; `width` comes back as the bytes consumed.
unsigned decode_utf8(const std::string& text,std::size_t index,std::size_t& width) {
    const unsigned char lead=static_cast<unsigned char>(text[index]);
    unsigned code=lead;
    width=1;
    if(lead>=0xF0) {code=lead&0x07u;width=4;}
    else if(lead>=0xE0) {code=lead&0x0Fu;width=3;}
    else if(lead>=0xC0) {code=lead&0x1Fu;width=2;}
    if(width>1) {
        if(index+width>text.size()) {width=1;return lead;}
        for(std::size_t k=1;k<width;++k) {
            const unsigned char next=static_cast<unsigned char>(text[index+k]);
            if((next&0xC0u)!=0x80u) {width=1;return lead;}
            code=(code<<6)|(next&0x3Fu);
        }
    }
    return code;
}
bool blank_after_strip(const std::string& text) {
    std::size_t index=0;
    while(index<text.size()) {
        std::size_t width=0;
        const unsigned code=decode_utf8(text,index,width);
        if(!unicode_space(code)) return false;
        index+=width;
    }
    return true;
}
// `str.isdigit()` restricted to ASCII, plus `int(text)`. The registry's biome keys are
// authored as plain decimal strings; an exotic digit would be an authoring accident.
bool decimal_key(const std::string& text,std::int64_t& out) {
    if(text.empty()) return false;
    for(const char c:text) if(c<'0'||c>'9') return false;
    out=0;
    for(const char c:text) {
        if(out>(std::numeric_limits<std::int64_t>::max()-(c-'0'))/10) return false;
        out=out*10+(c-'0');
    }
    return true;
}
// ---------------------------------------------------------------------------
// Reader. Strict JSON plus the NaN/Infinity literals CPython's json module accepts,
// and `_unique_object`, which rejects a repeated key rather than merging it. The hook
// only runs when its object closes, so an inner duplicate always reports before an
// outer one; the port collects the pairs first for exactly that reason.
// ---------------------------------------------------------------------------
struct Reader {
    const std::string& raw;
    std::size_t pos=0,depth=0;
    [[noreturn]] void fail() const {value_error("Invalid registry JSON");}
    void space() {
        while(pos<raw.size()&&(raw[pos]==' '||raw[pos]=='\t'||raw[pos]=='\r'||raw[pos]=='\n')) ++pos;
    }
    bool take(char c) {if(pos<raw.size()&&raw[pos]==c) {++pos;return true;} return false;}
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
                    if(code>=0xD800&&code<=0xDBFF&&pos+2<=raw.size()&&raw[pos]=='\\'&&raw[pos+1]=='u') {
                        const std::size_t mark=pos;
                        pos+=2;
                        const unsigned low=hex_quad();
                        if(low>=0xDC00&&low<=0xDFFF) code=0x10000+((code-0xD800)<<10)+(low-0xDC00);
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
    Value number_value() {
        const std::size_t start=pos;
        bool real=false;
        if(pos<raw.size()&&raw[pos]=='-') ++pos;
        if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
        while(pos<raw.size()&&raw[pos]>='0'&&raw[pos]<='9') ++pos;
        if(pos<raw.size()&&raw[pos]=='.') {
            real=true;++pos;
            if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
            while(pos<raw.size()&&raw[pos]>='0'&&raw[pos]<='9') ++pos;
        }
        if(pos<raw.size()&&(raw[pos]=='e'||raw[pos]=='E')) {
            real=true;++pos;
            if(pos<raw.size()&&(raw[pos]=='+'||raw[pos]=='-')) ++pos;
            if(pos>=raw.size()||raw[pos]<'0'||raw[pos]>'9') fail();
            while(pos<raw.size()&&raw[pos]>='0'&&raw[pos]<='9') ++pos;
        }
        const std::string token=raw.substr(start,pos-start);
        Value node;
        node.number=std::strtod(token.c_str(),nullptr);
        if(real) {node.kind=Value::Kind::Float;return node;}
        node.kind=Value::Kind::Int;
        errno=0;
        char* end=nullptr;
        const long long parsed=std::strtoll(token.c_str(),&end,10);
        if(errno==0&&end!=nullptr&&*end=='\0') {
            node.whole=static_cast<std::int64_t>(parsed);
            node.whole_fits=true;
            // str(int) and the literal agree except for "-0", which Python renders "0".
            node.text=std::to_string(node.whole);
        } else node.text=token;
        return node;
    }
    Value value() {
        if(++depth>200) fail();
        space();
        if(pos>=raw.size()) fail();
        Value node;
        const char c=raw[pos];
        if(c=='{') {
            ++pos;
            node.kind=Value::Kind::Object;
            space();
            if(!take('}')) {
                while(true) {
                    space();
                    std::string key=string_value();
                    space();expect(':');
                    node.fields.emplace_back(std::move(key),value());
                    space();
                    if(take('}')) break;
                    expect(',');
                }
            }
            // `_unique_object(pairs)` runs here, once the object is complete.
            std::set<std::string> seen;
            for(const auto& entry:node.fields)
                if(!seen.insert(entry.first).second)
                    value_error("Duplicate registry key: "+entry.first);
        } else if(c=='[') {
            ++pos;
            node.kind=Value::Kind::Array;
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
            node.kind=Value::Kind::String;
            node.text=string_value();
        } else if(literal("true")) {node.kind=Value::Kind::Bool;node.boolean=true;}
        else if(literal("false")) {node.kind=Value::Kind::Bool;node.boolean=false;}
        else if(literal("null")) {node.kind=Value::Kind::Null;}
        else if(literal("NaN")) {node.kind=Value::Kind::Float;node.number=std::numeric_limits<double>::quiet_NaN();}
        else if(literal("Infinity")) {node.kind=Value::Kind::Float;node.number=std::numeric_limits<double>::infinity();}
        else if(literal("-Infinity")) {node.kind=Value::Kind::Float;node.number=-std::numeric_limits<double>::infinity();}
        else node=number_value();
        --depth;
        return node;
    }
};
// json.dumps with ensure_ascii=False: only the backslash, the quote and the C0
// controls are escaped; everything above them, DEL and all of UTF-8 included, is
// written through untouched.
void escape(const std::string& value,std::string& out) {
    out+='"';
    for(std::size_t index=0;index<value.size();++index) {
        const unsigned char c=static_cast<unsigned char>(value[index]);
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
    }
    out+='"';
}
void dump_into(const Value& node,std::string& out) {
    switch(node.kind) {
        case Value::Kind::Null: out+="null";return;
        case Value::Kind::Bool: out+=node.boolean?"true":"false";return;
        case Value::Kind::Int: out+=node.text;return;
        case Value::Kind::Float: out+=py_repr(node.number);return;
        case Value::Kind::String: escape(node.text,out);return;
        case Value::Kind::Array: {
            out+='[';
            for(std::size_t i=0;i<node.items.size();++i) {
                if(i) out+=',';
                dump_into(node.items[i],out);
            }
            out+=']';
            return;
        }
        case Value::Kind::Object: {
            out+='{';
            for(std::size_t i=0;i<node.fields.size();++i) {
                if(i) out+=',';
                escape(node.fields[i].first,out);
                out+=':';
                dump_into(node.fields[i].second,out);
            }
            out+='}';
            return;
        }
    }
}
// ---------------------------------------------------------------------------
// terrain_profiles.validate_habitat / validate_profile
// ---------------------------------------------------------------------------
void validate_habitat(const Value& rule,int depth=0) {
    if(rule.kind!=Value::Kind::Object||depth>8) value_error("Invalid habitat rule");
    if(rule.fields.empty()) return;
    for(const char* op:{"all","any"}) {
        const Value* children=rule.find(op);
        if(children==nullptr) continue;
        if(rule.fields.size()!=1||children->kind!=Value::Kind::Array||children->items.empty())
            value_error("Invalid habitat combination");
        for(const Value& child:children->items) validate_habitat(child,depth+1);
        return;
    }
    static const std::set<std::string> habitat_fields={
        "biome","variant","temperature","moisture","maritime","landmass_area_m2",
        "landmass_fraction","largest_landmass","resource","slope","height","tpi",
        "coastal_support","abs_latitude"};
    const Value* field=rule.find("field");
    if(field==nullptr||!field->is_string()||habitat_fields.count(field->text)==0)
        value_error("Unknown habitat field");
    static const std::set<std::string> allowed={"field","in","min","max","gt","equals"};
    bool extra=false;
    for(const auto& entry:rule.fields) if(allowed.count(entry.first)==0) extra=true;
    if(extra||rule.fields.size()<2) value_error("Invalid habitat comparison");
    for(const char* key:{"min","max","gt"}) {
        const Value* bound=rule.find(key);
        if(bound!=nullptr&&!finite_number(*bound)) value_error("Invalid habitat bound");
    }
    const Value* low=rule.find("min");
    const Value* high=rule.find("max");
    if(low!=nullptr&&high!=nullptr&&as_double(*low)>as_double(*high))
        value_error("Reversed habitat bounds");
    const Value* members=rule.find("in");
    if(members!=nullptr) {
        bool bad=members->kind!=Value::Kind::Array||members->items.empty();
        if(!bad) for(const Value& item:members->items) {
            if(item.is_string()) continue;
            const bool numeric=item.kind==Value::Kind::Int||item.kind==Value::Kind::Float
                               ||item.kind==Value::Kind::Bool;
            if(!numeric||!std::isfinite(as_double(item))) {bad=true;break;}
        }
        if(bad) value_error("Invalid habitat membership");
    }
    const Value* equals=rule.find("equals");
    if(equals!=nullptr) {
        const bool numeric=equals->kind==Value::Kind::Int||equals->kind==Value::Kind::Float
                           ||equals->kind==Value::Kind::Bool;
        if(!numeric||!std::isfinite(as_double(*equals))) value_error("Invalid habitat equality");
    }
}
// What validate_registry actually reads back out of the validated profile.
struct ProfileIdentity {
    std::string kind;
    bool structure_blocks_is_null=true;
    std::string structure_blocks;
};
ProfileIdentity validate_profile(const Value& raw,const std::string& profile_id) {
    std::set<std::string> wanted=profile_fields();
    wanted.insert("civilization");
    if(key_set(raw)!=wanted)
        value_error("Civilization requires a complete independent trait record");
    const Value& identity=raw.at("civilization");
    const Value* kind=identity.kind==Value::Kind::Object?identity.find("kind"):nullptr;
    if(identity.kind!=Value::Kind::Object||kind==nullptr||!kind->is_string()
       ||(kind->text!="entity"&&kind->text!="aggregate"))
        value_error("Invalid civilization identity");
    static const std::set<std::string> identity_fields={
        "kind","inspiration","environment","habitat","allocation_group","priority","structure_blocks"};
    if(key_set(identity)!=identity_fields) value_error("Incomplete civilization identity");
    const Value& priority=identity.at("priority");
    if(!is_int(priority)||as_double(priority)<0.) value_error("Invalid habitat priority");
    for(const char* key:{"inspiration","allocation_group","structure_blocks"}) {
        const Value& label=identity.at(key);
        if(label.kind==Value::Kind::Null) continue;
        if(!label.is_string()||label.text.empty()) value_error("Invalid civilization label");
    }
    const Value& environment=identity.at("environment");
    if(!environment.is_string()||environment.text.empty())
        value_error("Missing civilization environment");
    validate_habitat(identity.at("habitat"));
    // `result={k:v for k,v in raw.items() if k!='civilization'};result['id']=profile_id`
    // -- insertion order decides which trait reports first, so the walk keeps it.
    std::vector<std::pair<std::string,const Value*>> result;
    for(const auto& entry:raw.fields)
        if(entry.first!="civilization") result.emplace_back(entry.first,&entry.second);
    const Value id_value=Value::make_string(profile_id);
    result.emplace_back("id",&id_value);
    static const std::set<std::string> text_keys={"name","description","id"};
    static const std::set<std::string> biome_keys={"biome_preferences","food_biome_multipliers",
        "magic_biome_preferences","food_magic_biome_multipliers"};
    for(const auto& entry:result) {
        const std::string& k=entry.first;
        const Value& v=*entry.second;
        if(text_keys.count(k)) {
            if(!v.is_string()||v.text.empty()) value_error("Invalid profile text");
        } else if(biome_keys.count(k)) {
            if(v.kind!=Value::Kind::Object) value_error("Invalid biome mapping");
            const bool magical=k.find("magic_biome")!=std::string::npos;
            const bool preference=k.size()>=11&&k.compare(k.size()-11,11,"preferences")==0;
            for(const auto& pair:v.fields) {
                bool valid;
                if(magical) valid=variant_ids().count(pair.first)!=0;
                else {
                    std::int64_t core=0;
                    valid=decimal_key(pair.first,core)&&natural_biomes().count(core)!=0;
                }
                if(!valid||!finite_number(pair.second)) value_error("Invalid biome trait");
                const double weight=as_double(pair.second);
                const bool ok=preference?(-1.<=weight&&weight<=1.):(0.<=weight&&weight<=2.);
                if(!ok) value_error("Invalid biome multiplier");
            }
        } else if(!finite_number(v)) value_error("Invalid numeric profile trait");
    }
    auto trait=[&](const char* key)->double{return as_double(raw.at(key));};
    for(const char* k:{"temperature_tolerance","slope_comfort","site_slope_limit","work_slope_limit",
                       "water_reach","food_temperature_tolerance","food_slope_comfort",
                       "land_per_city_km2","support_multiplier","college_water_reach"})
        if(trait(k)<=0.) value_error(std::string(k)+" must be positive");
    for(const char* k:{"mutation_limit","difficult_fraction","irrigation","moisture_ideal",
                       "food_moisture_ideal","college_flood_limit","college_suitability_min"})
        if(!(0.<=trait(k)&&trait(k)<=1.)) value_error(std::string(k)+" must be 0..1");
    if(trait("food_moisture_ideal")==0.||!(.01<=trait("road_grade_limit")&&trait("road_grade_limit")<=1.))
        value_error("Invalid profile reach or moisture");
    if(trait("college_temperature_min")>=trait("college_temperature_max"))
        value_error("Invalid college climate range");
    for(const char* k:{"water_weight","slope_weight","climate_weight","moisture_weight",
                       "resource_weight","flood_penalty","magic_penalty"})
        if(!(0.<=trait(k)&&trait(k)<=1.)) value_error(std::string(k)+" must be 0..1");
    for(const char* k:{"site_slope_limit","work_slope_limit","college_slope_limit","slope_comfort",
                       "food_slope_comfort"})
        if(!(0.<trait(k)&&trait(k)<90.)) value_error(std::string(k)+" must be between 0 and 90 degrees");
    if(!(0.<=trait("food_demand")&&trait("food_demand")<=10000.))
        value_error("Food demand out of range");
    if(!(.01<=trait("land_per_city_km2")&&trait("land_per_city_km2")<=1000.)
       ||!(0.<trait("support_multiplier")&&trait("support_multiplier")<=10.))
        value_error("Population footprint out of range");
    const Value& founding=raw.at("minimum_founding_residents");
    if(!is_int(founding)||!within(founding,1,10000)) value_error("Invalid founding minimum");
    if(!(-100.<=trait("food_temperature_ideal")&&trait("food_temperature_ideal")<=100.))
        value_error("Invalid food temperature ideal");
    ProfileIdentity out;
    out.kind=kind->text;
    const Value& blocks=identity.at("structure_blocks");
    out.structure_blocks_is_null=blocks.kind==Value::Kind::Null;
    if(!out.structure_blocks_is_null) out.structure_blocks=blocks.text;
    return out;
}
// ---------------------------------------------------------------------------
// civilization_registry validation
// ---------------------------------------------------------------------------
void validate_staffing(const Value& staff) {
    static const std::set<std::string> wanted={"basis","housing_location","roles","notes"};
    if(key_set(staff)!=wanted) value_error("Invalid staffing basis");
    const Value& basis=staff.at("basis");
    if(!basis.is_string()||basis.text!="distinct_people_all_shifts") value_error("Invalid staffing basis");
    const Value& location=staff.at("housing_location");
    if(!location.is_string()||(location.text!="city"&&location.text!="hinterland"))
        value_error("Invalid worker housing location");
    const Value& notes=staff.at("notes");
    if(!notes.is_string()||notes.text.empty()) value_error("Missing staffing notes");
    const Value& roles=staff.at("roles");
    if(roles.kind!=Value::Kind::Array) value_error("Invalid staffing roles");
    std::set<std::string> seen;
    for(const Value& role:roles.items) {
        static const std::set<std::string> role_keys={"role","minimum","target","maximum"};
        const Value* name=role.kind==Value::Kind::Object?role.find("role"):nullptr;
        if(key_set(role)!=role_keys||name==nullptr||!name->is_string()||name->text.empty()
           ||seen.count(name->text)!=0)
            value_error("Invalid or duplicate staffing role");
        seen.insert(name->text);
        std::int64_t values[3];
        bool bad=false;
        for(int i=0;i<3;++i) {
            const Value& level=role.at(staff_levels[i]);
            if(!is_int(level)||!level.whole_fits||!within(level,0,10000)) {bad=true;values[i]=0;}
            else values[i]=level.whole;
        }
        if(bad||values[0]>values[1]||values[1]>values[2]||values[2]==0)
            value_error("Invalid staffing range");
    }
}
void check_finite(const Value& value) {
    if(value.kind==Value::Kind::Object) {
        for(const auto& entry:value.fields) check_finite(entry.second);
    } else if(value.kind==Value::Kind::Array) {
        for(const Value& child:value.items) check_finite(child);
    } else if(value.kind==Value::Kind::Float&&!std::isfinite(value.number))
        value_error("Registry numbers must be finite");
}
void number_check(const Value& value,double low,double high,const std::string& label,bool nullable=false) {
    if(nullable&&value.kind==Value::Kind::Null) return;
    if(!is_number(value)||!std::isfinite(as_double(value))||!within(value,low,high))
        value_error("Invalid registry "+label);
}
// `a+b+c` under Python's numeric tower: exact while every term is an int, double once
// any of them is a float. The registry compares the result against the authored plot.
Value add3(const Value& a,const Value& b,const Value& c) {
    if(is_int(a)&&is_int(b)&&is_int(c)&&a.whole_fits&&b.whole_fits&&c.whole_fits)
        return Value::make_int(a.whole+b.whole+c.whole);
    return Value::make_float((as_double(a)+as_double(b))+as_double(c));
}
void validate_settlement_blocks(const Value& entity,const Value& libraries,
                                const std::vector<std::string>& tiers,const std::string& label) {
    std::map<std::string,const Value*> structures;
    for(const Value& key:entity.at("buildings").at("structure_block_ids").items) {
        const Value* library=libraries.kind==Value::Kind::Object?libraries.find(key.text):nullptr;
        if(library==nullptr) key_error(key.text);
        for(const Value& block:library->at("blocks").items)
            for(const Value& s:block.at("structures").items) structures[s.at("id").text]=&s;
    }
    const std::string capitalized=label.empty()?label
        :std::string(1,static_cast<char>(std::toupper(static_cast<unsigned char>(label[0]))))+label.substr(1);
    for(const std::string& tier:tiers) {
        const Value& plan=entity.at(tier);
        const Value& status=plan.at("status");
        const Value& housing=plan.at("housing_status");
        if(!status.is_string()||status.text!="preconfigured_design"
           ||!housing.is_string()||housing.text!="deferred")
            value_error("Unsupported "+label+" plan status");
        for(const char* group:{"buildings","infrastructure"}) {
            const Value& entries=plan.at(group);
            if(entries.kind!=Value::Kind::Array||entries.items.empty())
                value_error("Empty "+label+" plan group");
            std::set<std::string> seen;
            for(const Value& entry:entries.items) {
                const std::string& sid=entry.at("structure_id").text;
                const auto found=structures.find(sid);
                if(found==structures.end()||seen.count(sid)!=0)
                    value_error("Unknown or duplicate "+label+" structure");
                seen.insert(sid);
                const Value& structure=*found->second;
                const Value* entry_staffing=entry.find("staffing");
                if(entry_staffing!=nullptr) validate_staffing(*entry_staffing);
                if(std::strcmp(group,"infrastructure")==0) {
                    const Value& staffing=entry_staffing!=nullptr?*entry_staffing:structure.at("staffing");
                    if(truthy(staffing.at("roles")))
                        value_error("Linear infrastructure uses shared service crews");
                }
                const Value& family=structure.at("module_family");
                if(family.is_string()&&family.text=="housing") value_error("Housing is deferred");
                const Value& conditions=entry.at("placement_conditions");
                if(conditions.kind!=Value::Kind::Array||!string_set_subset(conditions,placement_conditions()))
                    value_error("Invalid "+label+" placement condition");
                const Value& geometry=structure.at("geometry_type");
                if(std::strcmp(group,"buildings")==0) {
                    if(geometry.is_string()&&geometry.text=="linear_segment")
                        value_error("Linear structure needs route sizing");
                    const Value& count=entry.at("count");
                    if(!is_int(count)||!within(count,1,10000))
                        value_error("Invalid "+label+" building count");
                    const Value& name=entry.at("name");
                    if(!name.is_string()||blank_after_strip(name.text))
                        value_error("Missing "+label+" building name");
                } else {
                    // `structure['geometry_type']!='linear_segment' or entry['quantity_mode']!=...`
                    // short-circuits, so a non-linear structure never reaches the
                    // subscript that would raise a KeyError for a missing mode.
                    bool bad=!geometry.is_string()||geometry.text!="linear_segment";
                    if(!bad) {
                        const Value& mode=entry.at("quantity_mode");
                        bad=!mode.is_string()||mode.text!="fit_route_or_perimeter";
                    }
                    if(bad) value_error("Invalid "+label+" infrastructure sizing");
                }
                const Value& size=structure.at("dimensions_m");
                const Value& clear=structure.at("clearance_m");
                const Value& plot=structure.at("plot_m");
                number_check(size.at("width"),.01,100000,"structure dimension");
                number_check(size.at("depth"),.01,100000,"structure dimension");
                number_check(plot.at("width"),.01,100000,"structure dimension");
                number_check(plot.at("depth"),.01,100000,"structure dimension");
                number_check(size.at("height"),0,100000,"structure height");
                for(const char* side:{"left","right","front","rear"})
                    number_check(clear.at(side),0,100000,"structure clearance");
                const Value width=add3(size.at("width"),clear.at("left"),clear.at("right"));
                const Value depth=add3(size.at("depth"),clear.at("front"),clear.at("rear"));
                if(!py_equal(plot.at("width"),width)||!py_equal(plot.at("depth"),depth))
                    value_error(capitalized+" structure plot does not include its clearances");
            }
        }
    }
}
void validate_registry_body(const Value& data) {
    const Value& entities=data.at("entities");
    const Value& configs=data.at("configurations");
    const Value& founding=data.at("founding_rules");
    number_check(founding.at("years_per_round"),1,10000,"years per founding round");
    number_check(founding.at("diaspora_interval_years"),1,100000,"diaspora interval");
    {
        const Value& interval=founding.at("diaspora_interval_years");
        const Value& round=founding.at("years_per_round");
        bool aligned;
        if(is_int(interval)&&is_int(round)&&interval.whole_fits&&round.whole_fits&&round.whole!=0) {
            // Python's % floors toward negative infinity and takes the divisor's sign.
            std::int64_t remainder=interval.whole%round.whole;
            if(remainder!=0&&((remainder<0)!=(round.whole<0))) remainder+=round.whole;
            aligned=remainder==0;
        } else {
            const double divisor=as_double(round);
            double remainder=std::fmod(as_double(interval),divisor);
            if(remainder!=0.&&((remainder<0.)!=(divisor<0.))) remainder+=divisor;
            aligned=remainder==0.;
        }
        if(!aligned) value_error("Diaspora interval must align with founding rounds");
    }
    const Value& bonus=founding.at("diaspora_bonus_per_parent");
    if(!is_int(bonus)||!bonus.whole_fits||(bonus.whole!=0&&bonus.whole!=1))
        value_error("Diaspora bonus must be zero or one");
    number_check(founding.at("origin_min_separation_degrees"),0,180,"origin angular separation");
    const Value& parents=data.at("parent_races");
    if(parents.kind!=Value::Kind::Object||parents.fields.empty())
        value_error("Missing parent race blocks");
    for(const auto& entry:parents.fields) {
        const Value& parent=entry.second;
        number_check(parent.at("founding_participation_percent"),0,100,"founding participation percent");
        const Value* name=parent.kind==Value::Kind::Object?parent.find("name"):nullptr;
        if(!lower_identifier(entry.first)||name==nullptr||!name->is_string()||name->text.empty())
            value_error("Invalid parent race");
    }
    const Value& houses=data.at("housing_profiles");
    for(const char* housing_key:{"worker_house","worker_apartment","hamlet_house"}) {
        const Value& house=houses.at(housing_key);
        const Value& house_id=house.at("id");
        const Value& beds=house.at("worker_beds");
        if(!house_id.is_string()||house_id.text!=std::string("building.")+housing_key
           ||!is_int(beds)||!within(beds,1,32))
            value_error("Invalid housing capacity");
        for(const char* key:{"width","depth"}) {
            number_check(house.at("dimensions_m").at(key),1,100,"housing footprint");
            number_check(house.at("plot_m").at(key),as_double(house.at("dimensions_m").at(key)),200,
                         "housing plot");
        }
        number_check(house.at("dimensions_m").at("height"),1,100,"housing height");
    }
    if(!py_equal(houses.at("worker_apartment").at("plot_m"),houses.at("worker_house").at("plot_m"))
       ||as_double(houses.at("worker_apartment").at("worker_beds"))
          <=as_double(houses.at("worker_house").at("worker_beds")))
        value_error("Apartment densification requires the same plot and higher capacity");
    const Value& blocks=data.at("structure_blocks");
    if(blocks.kind!=Value::Kind::Object) key_error("structure_blocks");
    for(const auto& entry:blocks.fields)
        for(const Value& block:entry.second.at("blocks").items)
            for(const Value& structure:block.at("structures").items) {
                validate_staffing(structure.at("staffing"));
                const Value& geometry=structure.at("geometry_type");
                if(geometry.is_string()&&geometry.text=="linear_segment"
                   &&truthy(structure.at("staffing").at("roles")))
                    value_error("Linear infrastructure uses shared service crews");
            }
    if(entities.kind!=Value::Kind::Object||entities.fields.empty()||entities.fields.size()>128)
        value_error("Expected 1..128 civilization entities");
    {
        const std::set<std::string> a=key_set(entities),b=key_set(configs);
        for(const std::string& key:a) if(b.count(key)) value_error("Entity/configuration IDs collide");
    }
    for(const auto& entry:entities.fields)
        if(!lower_identifier(entry.first)) value_error("Invalid civilization ID");
    for(const auto& entry:configs.fields)
        if(!lower_identifier(entry.first)) value_error("Invalid civilization ID");
    {
        const Value& defaults=data.at("defaults");
        const Value& profile=defaults.at("profile_id");
        const Value& aggregate=defaults.at("aggregate_profile_id");
        const bool known=profile.is_string()&&entities.has(profile.text);
        const bool aggregate_known=aggregate.is_string()&&configs.kind==Value::Kind::Object
                                   &&configs.has(aggregate.text);
        if(!known||!aggregate_known) value_error("Invalid registry default");
    }
    const Value& classes=data.at("city_classification");
    number_check(classes.at("medium_suitability_min"),0,1,"medium threshold");
    const Value& policy=classes.at("capital_policy");
    if(!policy.is_string()
       ||policy.text!="retain_founding_capital_else_highest_suitability_then_lowest_node")
        value_error("Unsupported capital policy");
    const Value& packs=data.at("building_packs").at("packs");
    const Value& layouts=data.at("layout_profiles").at("profiles");
    std::map<std::string,std::set<std::string>> pack_index;
    for(const Value& pack:packs.items) {
        std::set<std::string> options;
        for(const Value& option:pack.at("building_options").items) options.insert(option.at("id").text);
        pack_index[pack.at("id").text]=options;
    }
    std::map<std::string,std::set<std::string>> layout_index;
    for(const Value& layout:layouts.items) {
        std::set<std::string> features;
        for(const auto& entry:layout.at("features").fields) features.insert(entry.first);
        layout_index[layout.at("id").text]=features;
    }
    if(pack_index.size()!=packs.items.size()||layout_index.size()!=layouts.items.size())
        value_error("Duplicate library ID");
    {
        const Value& pack_fallback=data.at("building_packs").at("fallback_pack_id");
        const Value& layout_fallback=data.at("layout_profiles").at("fallback_profile_id");
        if(!pack_fallback.is_string()||pack_index.count(pack_fallback.text)==0
           ||!layout_fallback.is_string()||layout_index.count(layout_fallback.text)==0)
            value_error("Invalid library fallback");
    }
    for(const Value& pack:packs.items) {
        std::set<std::string> options;
        for(const Value& option:pack.at("building_options").items) options.insert(option.at("id").text);
        if(options.size()!=pack.at("building_options").items.size())
            value_error("Duplicate building option");
        const Value* layout=pack.kind==Value::Kind::Object?pack.find("layout_profile_id"):nullptr;
        if(layout!=nullptr&&layout->kind!=Value::Kind::Null
           &&(!layout->is_string()||layout_index.count(layout->text)==0))
            value_error("Unknown pack layout");
    }
    for(const auto& item:entities.fields) {
        const std::string& key=item.first;
        const Value& entity=item.second;
        std::set<std::string> wanted={"parent_race_id","population","settlement","economy","sky",
                                      "presentation","buildings",hamlet_block};
        for(const char* block:city_blocks) wanted.insert(block);
        if(key_set(entity)!=wanted) value_error("Incomplete civilization entity");
        const Value& race=entity.at("parent_race_id");
        if(!race.is_string()||!parents.has(race.text)) value_error("Unknown parent race");
        const ProfileIdentity population=validate_profile(entity.at("population"),key);
        if(population.kind!="entity") value_error("Entity must declare entity kind");
        const Value& rules=entity.at("settlement");
        const Value& economy=entity.at("economy");
        validate_habitat(rules.at("surface_habitat"));
        validate_habitat(rules.at("world_habitat"));
        number_check(rules.at("freshwater_reach_multiplier"),0,100,"freshwater multiplier",true);
        if(rules.at("support_outside_habitat").kind!=Value::Kind::Bool)
            value_error("Invalid support policy");
        for(const char* field:{"coastal_score_weight","resource_score_weight"})
            number_check(rules.at(field),0,2,field);
        const Value& reason=rules.at("reason");
        if(reason.kind!=Value::Kind::Null&&!reason.is_string()) value_error("Invalid site reason");
        number_check(economy.at("winter_fishing_fraction"),0,1,"winter fishing fraction");
        number_check(economy.at("fishing_reach_multiplier"),.01,10,"fishing reach");
        for(const char* field:{"industrial_resource_min","air_terminal_resource_min"})
            number_check(economy.at(field),0,1,field,true);
        number_check(entity.at("sky").at("score_bias"),-100,100,"sky bias");
        number_check(entity.at("sky").at("moisture_score_weight"),-100,100,"sky moisture");
        for(const char* field:{"map_color_rgb","wall_color_rgb","roof_color_rgb"}) {
            const Value& color=entity.at("presentation").at(field);
            bool bad=color.kind!=Value::Kind::Array||color.items.size()!=3;
            if(!bad) for(const Value& channel:color.items)
                if(!is_int(channel)||!within(channel,0,255)) {bad=true;break;}
            if(bad) value_error("Invalid display color");
        }
        if(entity.at("presentation").at("outpost_colors").kind!=Value::Kind::Bool)
            value_error("Invalid outpost display flag");
        const Value& buildings=entity.at("buildings");
        for(const auto& binding:buildings.at("packs").fields) {
            const auto known=pack_index.find(binding.first);
            const Value& options=binding.second;
            bool bad=known==pack_index.end()||options.kind!=Value::Kind::Array;
            if(!bad) {
                std::set<std::string> unique;
                for(const Value& option:options.items) {
                    if(!option.is_string()) {bad=true;break;}
                    unique.insert(option.text);
                }
                if(!bad&&(unique.size()!=options.items.size()
                          ||!string_set_subset(options,known->second))) bad=true;
            }
            if(bad) value_error("Unknown or duplicate building reference");
        }
        {
            const Value& fallback=data.at("building_packs").at("fallback_pack_id");
            if(!buildings.at("packs").has(fallback.text))
                value_error("Entity needs an explicit fallback pack binding");
        }
        for(const auto& binding:buildings.at("layout_features").fields) {
            const auto known=layout_index.find(binding.first);
            if(known==layout_index.end()||binding.second.kind!=Value::Kind::Array
               ||!string_set_subset(binding.second,known->second))
                value_error("Unknown layout feature reference");
        }
        {
            const std::set<std::string> libraries=key_set(blocks);
            bool subset=true;
            bool rural=false;
            for(const Value& name:buildings.at("structure_block_ids").items) {
                if(!name.is_string()||libraries.count(name.text)==0) subset=false;
                if(name.is_string()&&name.text=="rural") rural=true;
            }
            if(!subset) value_error("Unknown structure block library");
            if(!rural) value_error("Entity needs the rural hamlet structure library");
            if(!population.structure_blocks_is_null) {
                bool bound=false;
                for(const Value& name:buildings.at("structure_block_ids").items)
                    if(name.is_string()&&name.text==population.structure_blocks) bound=true;
                if(!bound) value_error("Structure block identity disagrees with bindings");
            }
        }
        validate_settlement_blocks(entity,blocks,
            std::vector<std::string>(std::begin(city_blocks),std::end(city_blocks)),"city");
        validate_settlement_blocks(entity,blocks,{hamlet_block},"hamlet");
    }
    for(const auto& entry:configs.fields)
        if(validate_profile(entry.second,entry.first).kind!="aggregate")
            value_error("Invalid aggregate configuration");
}
// ---------------------------------------------------------------------------
// Loading and linking
// ---------------------------------------------------------------------------
std::string& mutable_path() {
    static std::string path="Sim/icarus_sim/civilizations.json";
    return path;
}
std::string sibling(const std::string& path,const std::string& name) {
    const std::size_t cut=path.find_last_of("/\\");
    return cut==std::string::npos?name:path.substr(0,cut+1)+name;
}
// `repr(str)` for the filename CPython embeds in an OSError's message.
std::string py_repr_str(const std::string& text) {
    std::string out="'";
    for(const char raw:text) {
        const unsigned char c=static_cast<unsigned char>(raw);
        if(c=='\\') out+="\\\\";
        else if(c=='\'') out+="\\'";
        else if(c=='\n') out+="\\n";
        else if(c=='\r') out+="\\r";
        else if(c=='\t') out+="\\t";
        else out+=static_cast<char>(c);
    }
    return out+"'";
}
struct Stat {std::uintmax_t size=0;std::int64_t mtime=0;};
Stat stat_or_raise(const std::string& path) {
    std::error_code code;
    const std::filesystem::path handle=std::filesystem::u8path(path);
    const std::uintmax_t size=std::filesystem::file_size(handle,code);
    if(code) {
        // `Path.stat()` on Windows reports the Win32 fault, not the POSIX one.
        const bool directory=!std::filesystem::exists(handle.parent_path());
        throw RegistryError("OSError",directory
            ?"[WinError 3] The system cannot find the path specified: "+py_repr_str(path)
            :"[WinError 2] The system cannot find the file specified: "+py_repr_str(path));
    }
    Stat out;
    out.size=size;
    const auto stamp=std::filesystem::last_write_time(handle,code);
    out.mtime=code?0:static_cast<std::int64_t>(stamp.time_since_epoch().count());
    return out;
}
std::string read_text(const std::string& path) {
    std::ifstream stream(std::filesystem::u8path(path),std::ios::binary);
    if(!stream) throw RegistryError("OSError",
        "[WinError 2] The system cannot find the file specified: "+py_repr_str(path));
    return std::string((std::istreambuf_iterator<char>(stream)),std::istreambuf_iterator<char>());
}
struct CacheKey {
    std::string path;
    std::int64_t mtime=0;
    std::uintmax_t size=0;
    bool operator<(const CacheKey& other) const {
        if(path!=other.path) return path<other.path;
        if(mtime!=other.mtime) return mtime<other.mtime;
        return size<other.size;
    }
};
// `@lru_cache(maxsize=8)`: the parse is shared, keyed on path, modification time and
// size, exactly as the reference keys it, and bounded the same way so a host that
// walks many catalogues does not accumulate every one of them.
template<class Key,class Made>
const Value& bounded_cache(std::map<Key,Value>& cache,std::vector<Key>& order,
                           const Key& key,Made make) {
    const auto found=cache.find(key);
    if(found!=cache.end()) return found->second;
    Value built=make();
    while(order.size()>=8) {cache.erase(order.front());order.erase(order.begin());}
    order.push_back(key);
    return cache.emplace(key,std::move(built)).first->second;
}
const Value& read_cached(const std::string& path,const Stat& stat) {
    static std::map<CacheKey,Value> cache;
    static std::vector<CacheKey> order;
    const CacheKey key{path,stat.mtime,stat.size};
    return bounded_cache(cache,order,key,[&]{return loads(read_text(path));});
}
// `any(key in raw for key in (*BUILDING_SECTIONS,'building_catalogue_metadata'))`, which
// the reference tests before it reads the linked file at all.
void check_raw_sections(const Value& raw) {
    for(const char* key:building_sections)
        if(raw.has(key)) value_error("Building definitions must live in the linked buildings.json");
    if(raw.has("building_catalogue_metadata"))
        value_error("Building definitions must live in the linked buildings.json");
}
Value resolve_document(const Value& raw,const Value& buildings) {
    check_raw_sections(raw);
    const Value* schema=buildings.kind==Value::Kind::Object?buildings.find("schema"):nullptr;
    const Value* version=buildings.kind==Value::Kind::Object?buildings.find("schema_version"):nullptr;
    if(buildings.kind!=Value::Kind::Object
       ||schema==nullptr||!schema->is_string()||schema->text!="fantasy-world-generator.building-registry"
       ||version==nullptr||!is_int(*version)||!version->whole_fits||version->whole!=2)
        value_error("Unsupported building registry schema");
    const Value* revision=buildings.find("revision");
    if(revision==nullptr||!is_int(*revision)||!revision->whole_fits||revision->whole<1)
        value_error("Invalid building registry revision");
    for(const char* key:building_sections)
        if(!buildings.has(key)) value_error("Incomplete building registry");
    std::vector<std::string> ids;
    for(const auto& entry:buildings.at("structure_blocks").fields)
        for(const Value& block:entry.second.at("blocks").items)
            for(const Value& s:block.at("structures").items) ids.push_back(s.at("id").text);
    {
        const std::set<std::string> unique(ids.begin(),ids.end());
        bool bad=unique.size()!=ids.size();
        if(!bad) for(const std::string& sid:ids) if(!building_identifier(sid)) {bad=true;break;}
        if(bad) value_error("Invalid or duplicate neutral building ID");
    }
    {
        const Value* version_raw=raw.kind==Value::Kind::Object?raw.find("schema_version"):nullptr;
        const bool six=version_raw!=nullptr&&is_int(*version_raw)&&version_raw->whole_fits
                       &&version_raw->whole==6;
        if(!six||raw.has("entities"))
            value_error("Expected schema 5 with civilizations nested in parent race blocks");
    }
    Value data=raw;
    // `data['parent_races']` is replaced by a flat name/participation view and the
    // nested civilizations are hoisted into `data['entities']`, in the order the
    // authored `civilization_order` list names them.
    std::vector<std::pair<std::string,Value>> hoisted;
    Value parents=Value::make_object();
    try {
        const Value& races=data.at("parent_races");
        if(races.kind!=Value::Kind::Object) key_error("parent_races");
        for(const auto& entry:races.fields) {
            const Value& block=entry.second;
            Value summary=Value::make_object();
            summary.set("name",block.at("name"));
            summary.set("founding_participation_percent",block.at("founding_participation_percent"));
            parents.set(entry.first,std::move(summary));
            const Value& members=block.at("civilizations");
            if(members.kind!=Value::Kind::Object) key_error("civilizations");
            for(const auto& member:members.fields) {
                bool duplicate=false;
                for(const auto& seen:hoisted) if(seen.first==member.first) duplicate=true;
                if(duplicate||member.second.has("parent_race_id"))
                    value_error("Duplicate civilization or redundant parent race");
                Value copy=member.second;
                copy.set("parent_race_id",Value::make_string(entry.first));
                hoisted.emplace_back(member.first,std::move(copy));
            }
        }
        const Value& order=data.at("civilization_order");
        bool bad=order.kind!=Value::Kind::Array;
        std::set<std::string> named;
        if(!bad) for(const Value& name:order.items) {
            if(!name.is_string()) {bad=true;break;}
            named.insert(name.text);
        }
        if(!bad&&named.size()!=order.items.size()) bad=true;
        if(!bad) {
            std::set<std::string> available;
            for(const auto& entry:hoisted) available.insert(entry.first);
            if(named!=available) bad=true;
        }
        if(bad) value_error("Civilization order must name every nested entity exactly once");
        Value ordered=Value::make_object();
        for(const Value& name:order.items)
            for(const auto& entry:hoisted)
                if(entry.first==name.text) {ordered.set(name.text,entry.second);break;}
        data.set("entities",std::move(ordered));
        data.set("parent_races",std::move(parents));
    } catch(const RegistryError& error) {
        if(error.python_class=="KeyError") value_error("Malformed parent race blocks");
        throw;
    }
    for(const char* key:building_sections) data.set(key,buildings.at(key));
    Value metadata=Value::make_object();
    for(const auto& entry:buildings.fields) {
        bool section_key=false;
        for(const char* key:building_sections) if(entry.first==key) section_key=true;
        if(!section_key) metadata.set(entry.first,entry.second);
    }
    data.set("building_catalogue_metadata",std::move(metadata));
    validate_registry(data);
    return data;
}
// `_document()`: link the two shipped files, cached, wrapping the faults the reference
// wraps. A ValueError raised inside the pipeline passes through untouched; only the
// lookup and filesystem faults become the "Cannot load ..." sentence.
const Value& document_impl() {
    struct ResolveKey {
        CacheKey registry,buildings;
        bool operator<(const ResolveKey& other) const {
            if(registry<other.registry) return true;
            if(other.registry<registry) return false;
            return buildings<other.buildings;
        }
    };
    static std::map<ResolveKey,Value> cache;
    static std::vector<ResolveKey> order;
    const std::string path=mutable_path();
    try {
        const Stat stat=stat_or_raise(path);
        const Value& raw=read_cached(path,stat);
        Value expected=Value::make_object();
        expected.set("path",Value::make_string("buildings.json"));
        expected.set("schema_version",Value::make_int(2));
        const Value* link=raw.kind==Value::Kind::Object?raw.find("building_catalogue"):nullptr;
        if(link==nullptr||!py_equal(*link,expected))
            value_error("Expected a sibling buildings.json registry link with schema version 2");
        const std::string building_path=sibling(path,"buildings.json");
        const Stat building_stat=stat_or_raise(building_path);
        const ResolveKey key{{path,stat.mtime,stat.size},
                             {building_path,building_stat.mtime,building_stat.size}};
        // The reference reads the linked file only after the raw document is cleared
        // of building sections, so a fault there reports before one in buildings.json.
        return bounded_cache(cache,order,key,[&]{
            check_raw_sections(raw);
            return resolve_document(raw,read_cached(building_path,building_stat));
        });
    } catch(const RegistryError& error) {
        if(error.python_class=="OSError"||error.python_class=="KeyError")
            value_error(std::string("Cannot load linked civilization/building registries: ")+error.what());
        throw;
    }
}
// `_expand_settlement_plan(entity_id, block_name, block_key)`.
Value expand_settlement_plan(const std::string& entity_id,const std::string& block_name,
                             const std::string& block_key) {
    const Value& doc=document_impl();
    const Value& entities=doc.at("entities");
    if(!entities.has(entity_id)) value_error("Unknown civilization");
    const Value& entity=entities.at(entity_id);
    std::map<std::string,const Value*> structures;
    for(const Value& key:entity.at("buildings").at("structure_block_ids").items)
        for(const Value& block:doc.at("structure_blocks").at(key.text).at("blocks").items)
            for(const Value& s:block.at("structures").items) structures[s.at("id").text]=&s;
    Value plan=entity.at(block_name);
    for(const char* group:{"buildings","infrastructure"}) {
        Value rows=Value::make_array();
        for(const Value& row:plan.at(group).items) {
            // `{**structure, **row}`: the structure's key order wins, a shared key keeps
            // the structure's slot and takes the row's value, and the row's own keys
            // follow in the order it authored them.
            Value merged=*structures.at(row.at("structure_id").text);
            for(const auto& entry:row.fields) merged.set(entry.first,entry.second);
            rows.items.push_back(std::move(merged));
        }
        plan.set(group,std::move(rows));
    }
    static const char* const metrics[]={"workers","city_worker_beds","hinterland_worker_beds"};
    static const char* const groups[]={"unconditional","conditional","all_configured"};
    std::map<std::string,std::map<std::string,std::map<std::string,std::int64_t>>> totals;
    for(const char* group:groups)
        for(const char* metric:metrics)
            for(const char* level:staff_levels) totals[group][metric][level]=0;
    for(Value& row:plan.find("buildings")->items) {
        const Value& count=row.at("count");
        Value computed=staffing_totals(row.at("staffing"),count.whole);
        const bool conditional=truthy(row.at("placement_conditions"));
        const char* group=conditional?"conditional":"unconditional";
        for(const auto& metric:computed.fields)
            for(const auto& level:metric.second.fields) {
                totals[group][metric.first][level.first]+=level.second.whole;
                totals["all_configured"][metric.first][level.first]+=level.second.whole;
            }
        row.set("staffing_totals",std::move(computed));
    }
    Value summary=Value::make_object();
    for(const char* group:groups) {
        Value block=Value::make_object();
        for(const char* metric:metrics) {
            Value levels=Value::make_object();
            for(const char* level:staff_levels)
                levels.set(level,Value::make_int(totals[group][metric][level]));
            block.set(metric,std::move(levels));
        }
        summary.set(group,std::move(block));
    }
    summary.set("total_residents",Value::make_null());
    summary.set("houses_required",Value::make_null());
    summary.set("basis",Value::make_string(
        "One distinct resident worker per filled roster post; household members and "
        "housing occupancy not yet modeled."));
    plan.set("staffing_summary",std::move(summary));
    plan.set("civilization_id",Value::make_string(entity_id));
    plan.set("unit",Value::make_string("metres"));
    plan.set("runtime_placement_enabled",Value::make_bool(false));
    plan.set(block_key,Value::make_string(block_name));
    return plan;
}
}
// ---------------------------------------------------------------------------
// Value
// ---------------------------------------------------------------------------
const Value* Value::find(const std::string& key) const {
    for(const auto& entry:fields) if(entry.first==key) return &entry.second;
    return nullptr;
}
Value* Value::find(const std::string& key) {
    for(auto& entry:fields) if(entry.first==key) return &entry.second;
    return nullptr;
}
const Value& Value::at(const std::string& key) const {
    const Value* found=find(key);
    if(found==nullptr) key_error(key);
    return *found;
}
void Value::set(const std::string& key,Value child) {
    Value* found=find(key);
    if(found!=nullptr) {*found=std::move(child);return;}
    fields.emplace_back(key,std::move(child));
}
Value Value::make_null() {return Value();}
Value Value::make_bool(bool value) {
    Value node;node.kind=Kind::Bool;node.boolean=value;return node;
}
Value Value::make_int(std::int64_t value) {
    Value node;node.kind=Kind::Int;node.whole=value;node.whole_fits=true;
    node.number=static_cast<double>(value);node.text=std::to_string(value);return node;
}
Value Value::make_float(double value) {
    Value node;node.kind=Kind::Float;node.number=value;return node;
}
Value Value::make_string(std::string value) {
    Value node;node.kind=Kind::String;node.text=std::move(value);return node;
}
Value Value::make_array() {Value node;node.kind=Kind::Array;return node;}
Value Value::make_object() {Value node;node.kind=Kind::Object;return node;}

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
    const char* cursor=buffer;
    std::string sign;
    if(*cursor=='-') {sign="-";++cursor;}
    std::string digits;
    for(;*cursor&&*cursor!='e'&&*cursor!='E';++cursor) if(*cursor!='.') digits+=*cursor;
    const int exponent=(*cursor)?std::atoi(cursor+1):0;
    while(digits.size()>1&&digits.back()=='0') digits.pop_back();
    const int decpt=exponent+1;
    std::string out=sign;
    if(decpt<=-4||decpt>16) {
        out+=digits[0];
        if(digits.size()>1) {out+='.';out.append(digits,1,std::string::npos);}
        const int e=decpt-1;
        out+='e';
        out+=(e<0?'-':'+');
        char tail[16];
        std::snprintf(tail,sizeof tail,"%02d",e<0?-e:e);
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
std::string dumps(const Value& value) {
    std::string out;
    dump_into(value,out);
    return out;
}
Value loads(const std::string& text) {
    Reader reader{text};
    Value root=reader.value();
    reader.space();
    if(reader.pos!=text.size()) reader.fail();
    return root;
}
void set_registry_path(const std::string& path) {mutable_path()=path;}
const std::string& registry_path() {return mutable_path();}
const Value& document() {return document_impl();}
Value load_registry() {return document_impl();}
Value section(const std::string& name) {return document_impl().at(name);}
Value resolve(const std::string& registry_bytes,const std::string& buildings_bytes) {
    return resolve_document(loads(registry_bytes),loads(buildings_bytes));
}
void validate_registry(const Value& data) {
    const Value* schema=data.kind==Value::Kind::Object?data.find("schema"):nullptr;
    const Value* version=data.kind==Value::Kind::Object?data.find("schema_version"):nullptr;
    if(data.kind!=Value::Kind::Object
       ||schema==nullptr||!schema->is_string()
       ||schema->text!="fantasy-world-generator.civilization-registry"
       ||version==nullptr||!is_int(*version)||!version->whole_fits||version->whole!=6)
        value_error("Unsupported civilization registry schema");
    const Value* revision=data.find("revision");
    if(revision==nullptr||!is_int(*revision)||!revision->whole_fits||revision->whole<1)
        value_error("Invalid registry revision");
    check_finite(data);
    try {
        validate_registry_body(data);
    } catch(const RegistryError& error) {
        if(error.python_class=="KeyError")
            value_error(std::string("Malformed civilization registry: ")+error.what());
        throw;
    }
}
Identity registry_identity() {
    const Value& doc=document_impl();
    Identity out;
    out.schema_version=doc.at("schema_version").whole;
    out.revision=doc.at("revision").whole;
    out.sha256=sha256(dumps(doc));
    return out;
}
std::string default_profile_id() {return document_impl().at("defaults").at("profile_id").text;}
Value staffing_totals(const Value& staff,std::int64_t count) {
    validate_staffing(staff);
    if(!(0<=count&&count<=10000)) value_error("Invalid staffing instance count");
    const bool in_city=staff.at("housing_location").text=="city";
    Value workers=Value::make_object();
    std::map<std::string,std::int64_t> counted;
    for(const char* level:staff_levels) {
        std::int64_t total=0;
        for(const Value& role:staff.at("roles").items) total+=role.at(level).whole;
        counted[level]=count*total;
        workers.set(level,Value::make_int(counted[level]));
    }
    Value out=Value::make_object();
    out.set("workers",workers);
    Value city=Value::make_object(),hinterland=Value::make_object();
    for(const char* level:staff_levels) {
        city.set(level,Value::make_int(in_city?counted[level]:0));
        hinterland.set(level,Value::make_int(in_city?0:counted[level]));
    }
    out.set("city_worker_beds",std::move(city));
    out.set("hinterland_worker_beds",std::move(hinterland));
    return out;
}
Value city_plan(const std::string& entity_id,const std::string& city_block) {
    bool known=false;
    for(const char* block:city_blocks) if(city_block==block) known=true;
    if(!known) value_error("Unknown city size block");
    return expand_settlement_plan(entity_id,city_block,"city_block");
}
Value hamlet_plan(const std::string& entity_id) {
    return expand_settlement_plan(entity_id,hamlet_block,"settlement_block");
}
}
