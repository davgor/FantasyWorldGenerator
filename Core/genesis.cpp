#include "genesis.hpp"

namespace fantasy_world_generator {
namespace {
using json::Value;
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
bool digit(char c) {return c>='0' && c<='9';}
std::int64_t push(std::int64_t value,int added) {require(value<=(max_safe-added)/10);return value*10+added;}
// Exact decimal metres keep float rounding out of the Unreal centimetre frame.
std::int64_t decimal_centimetres(const std::string& text) {
    require(!text.empty() && text.size()<=max_offset_text);
    std::size_t pos=0;
    const bool negative=text[pos]=='-';
    if(negative) ++pos;
    const std::size_t start=pos;
    std::int64_t value=0;
    while(pos<text.size() && digit(text[pos])) value=push(value,text[pos++]-'0');
    require(pos>start && (pos-start==1 || text[start]!='0'));
    std::string fraction;
    if(pos<text.size()) {
        require(text[pos]=='.');++pos;
        while(pos<text.size() && digit(text[pos])) fraction+=text[pos++];
        require(!fraction.empty() && fraction.back()!='0');
    }
    // One centimetre is the finest exact source offset this slice transports.
    require(pos==text.size() && fraction.size()<=2);
    for(std::size_t place=0;place<2;++place) value=push(value,place<fraction.size() ? fraction[place]-'0' : 0);
    return negative ? -value : value;
}
}
std::int64_t source_centimetres(const json::Value& value) {
    if(auto metres=std::get_if<std::int64_t>(&value.data)) {
        require(*metres>=-max_metres && *metres<=max_metres);
        return *metres*centimetres_per_metre;
    }
    return decimal_centimetres(json::string(value));
}
UnrealPoint unreal_point(const json::Value& value) {
    json::exact(value,{"east_m","up_m","north_m"});
    // Unreal Y is source north and Unreal Z is source up; up is never Y.
    return UnrealPoint{source_centimetres(json::field(value,"east_m")),
                       source_centimetres(json::field(value,"north_m")),
                       source_centimetres(json::field(value,"up_m"))};
}
std::string unreal_point_json(const UnrealPoint& point) {
    return json::canonical(Value(Value::Array{Value(point.x_cm),Value(point.y_cm),Value(point.z_cm)}));
}
GenerateRequest generate_request(const json::Value& value) {
    const bool overridden=json::object(value).count("overrides")==1;
    if(overridden) json::exact(value,{"recipe_version","seed","overrides"});
    else json::exact(value,{"recipe_version","seed"});
    GenerateRequest request;
    request.recipe_version=json::integer(json::field(value,"recipe_version"));
    if(request.recipe_version!=genesis_recipe) throw Error("UNSUPPORTED_VERSION");
    request.seed=json::integer(json::field(value,"seed"));
    require(request.seed>=0 && request.seed<=max_seed);
    if(overridden) {
        const auto& overrides=json::field(value,"overrides");
        const auto& fields=json::object(overrides);
        for(const auto& pair:fields) require(pair.first=="size" || pair.first=="shape");
        if(fields.count("size")) {
            auto size=json::integer(json::field(overrides,"size"));
            if(size<min_grid || size>max_grid) throw Error("STATE_CAPACITY");
            request.size=size;
        }
        if(fields.count("shape")) {
            // Recipe 3 is a tectonic globe; a rectangular view is a tangent unwrap, not a shape.
            const auto& shape=json::string(json::field(overrides,"shape"));
            require(shape=="globe");
            request.shape=shape;
        }
    }
    return request;
}
std::string generate_request_json(const GenerateRequest& request) {
    return json::canonical(Value(Value::Object{{"ok",Value(true)},
        {"recipe_version",Value(request.recipe_version)},{"seed",Value(request.seed)}}));
}
}
