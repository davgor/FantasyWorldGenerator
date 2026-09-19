#include "genesis.hpp"
#include "config.hpp"
#include "globe.hpp"
#include <cmath>
#include <cstdlib>

namespace fantasy_world_generator {
namespace {
using json::Value;
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
// A scale arrives as characters and becomes the nearest double, which is what the
// reference does with the same characters. Anything the reference would reject, or
// any trailing rubbish, is a broken request rather than a rounded one.
double decimal_override(const std::string& text);
double decimal_scale(const std::string& text) {
    require(!text.empty() && text.size()<=max_offset_text);
    for(char c:text) require((c>='0' && c<='9') || c=='.' || c=='-' || c=='e' || c=='E' || c=='+');
    char* end=nullptr;
    const double value=std::strtod(text.c_str(),&end);
    require(end!=nullptr && *end=='\0' && std::isfinite(value));
    require(value>=min_world_scale && value<=max_world_scale);
    return value;
}
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
// An override arrives as characters and becomes the nearest double, the same value
// the reference reads from the same characters.
double decimal_override(const std::string& text) {
    require(!text.empty() && text.size()<=max_offset_text);
    for(char c:text) require((c>='0' && c<='9') || c=='.' || c=='-' || c=='e' || c=='E' || c=='+');
    char* end=nullptr;
    const double value=std::strtod(text.c_str(),&end);
    require(end!=nullptr && *end=='\0' && std::isfinite(value));
    return value;
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
        for(const auto& pair:fields)
            require(pair.first=="size" || pair.first=="shape" || pair.first=="world_scale"
                    || pair.first=="world_size" || override_bounds().count(pair.first)==1);
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
        for(const auto& pair:fields) {
            if(pair.first=="size" || pair.first=="shape" || pair.first=="world_scale"
               || pair.first=="world_size") continue;
            const auto bound=override_bounds().find(pair.first);
            require(bound!=override_bounds().end());
            const double value=decimal_override(json::string(pair.second));
            require(value>=bound->second.low && value<=bound->second.high);
            request.overrides.emplace(pair.first,value);
        }
        if(fields.count("world_size")) {
            const std::string& size=json::string(json::field(overrides,"world_size"));
            require(size=="small" || size=="medium" || size=="large");
            request.world_size=size;
        }
        if(fields.count("world_scale")) {
            // A decimal string, read to the nearest double exactly as the reference
            // reads the same characters, so a scaled world still replays bit for bit.
            request.world_scale=decimal_scale(json::string(json::field(overrides,"world_scale")));
        }
    }
    return request;
}
const std::map<std::string,OverrideBound>& override_bounds() {
    // The reference's own table, for the inputs this core resolves. Anything outside
    // a bound is a broken request, not a clamped one.
    static const std::map<std::string,OverrideBound> bounds{
        {"amplitude",{0.,1e7}},{"tectonic_relief",{0.,1e7}},{"mountain_detail",{0.,1.}},
        {"ridge",{0.,1.}},{"octaves",{1.,10.}},{"sea_level",{-1e7,1e7}},{"orogeny",{0.,20.}},{"globe_radius",{.01,1e7}},
        {"wavelength",{.01,1e7}},{"radius",{.01,1e7}},{"extent",{.01,1e7}},
        {"plate_count",{2.,64.}},{"belt_width",{.01,1.}},{"crust_bias",{-1.,1.}},
        {"temperature_offset",{-40.,40.}},{"moisture_bias",{-1.,1.}},
        {"erosion_passes",{0.,40.}},{"erosion_strength",{0.,1.}},
        {"settlement_spacing",{10.,10000.}},{"support_reach",{100.,10000.}},
    };
    return bounds;
}
std::map<std::string,double> orogeny_overrides(double gain) {
    require(std::isfinite(gain) && gain>0);
    std::map<std::string,double> overrides;
    overrides.emplace("orogeny",gain);
    for(const auto& entry:overrides) {
        const auto bound=override_bounds().find(entry.first);
        require(bound!=override_bounds().end());
        require(entry.second>=bound->second.low && entry.second<=bound->second.high);
    }
    return overrides;
}
std::map<std::string,double> world_shape_overrides(double circumference_m,double relief_m,double orogeny) {
    require(std::isfinite(circumference_m) && circumference_m>0);
    require(std::isfinite(relief_m) && relief_m>0);
    require(std::isfinite(orogeny) && orogeny>0);
    const WorldConfig recipe;
    std::map<std::string,double> overrides;
    // The scale stays the recipe's, so metres of relief mean the same thing at every
    // world width; the design radius carries the width instead.
    overrides.emplace("globe_radius",circumference_m/(2*pi*recipe.world_scale));
    const double tectonic=relief_m/recipe.world_scale;
    overrides.emplace("tectonic_relief",tectonic);
    overrides.emplace("amplitude",tectonic*(recipe.amplitude/recipe.tectonic_relief));
    overrides.emplace("orogeny",orogeny);
    for(const auto& entry:overrides) {
        const auto bound=override_bounds().find(entry.first);
        require(bound!=override_bounds().end());
        require(entry.second>=bound->second.low && entry.second<=bound->second.high);
    }
    return overrides;
}
double world_scale_for_circumference(double metres) {
    require(std::isfinite(metres) && metres>0);
    const WorldConfig design;
    const double scale=metres/(2*pi*design.globe_radius);
    require(scale>=min_world_scale && scale<=max_world_scale);
    return scale;
}
std::string generate_request_json(const GenerateRequest& request) {
    return json::canonical(Value(Value::Object{{"ok",Value(true)},
        {"recipe_version",Value(request.recipe_version)},{"seed",Value(request.seed)}}));
}
}
