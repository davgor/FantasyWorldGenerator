#pragma once
#include "json.hpp"
#include <map>
#include <string>
namespace fantasy_world_generator {
// Request boundary for world genesis. No Unreal, engine, asset or Python dependency:
// Unreal centimetres are plain integers here and a future adapter owns engine types.
constexpr std::int64_t genesis_recipe=3, max_seed=4294967295LL, min_grid=3, max_grid=257,
                      centimetres_per_metre=100, max_metres=max_safe/centimetres_per_metre;
constexpr std::size_t max_offset_text=24;
// The reference's own override range for the shared world scale, so a request cannot
// ask for a world the producer would refuse.
constexpr double min_world_scale=.001, max_world_scale=1000.;
// Unreal is left-handed and Z-up: source east is X, source north is Y, source up is Z.
struct UnrealPoint { std::int64_t x_cm=0, y_cm=0, z_cm=0; };
struct GenerateRequest {
    std::int64_t recipe_version=genesis_recipe, seed=0;
    std::optional<std::int64_t> size;
    std::optional<std::string> shape;
    // Physical size of the finished world: the shared scale the reference applies to
    // the design radius, so the same seed keeps its terrain and gains metres. The
    // unwrap a consumer presents is two pi r wide, which is how a world is asked for
    // in kilometres. Carried as a decimal string in the request document because this
    // domain's JSON is integer-only on purpose.
    std::optional<double> world_scale;
    // small, medium or large: the reference's design-radius preset, one, two or three
    // times ten kilometres. Belt widths are a fraction of that radius, so a larger
    // world does not just hold more, its tectonic features are physically wider.
    std::optional<std::string> world_size;
    // Recipe inputs a caller may override by name, with the reference's own bounds.
    // The terrain family is here because vertical relief is a design choice a game
    // makes: the recipe's default is a gentle world, and a caller that wants
    // mountains asks for them rather than exaggerating the result afterwards.
    std::map<std::string,double> overrides;
};
// Which inputs an override may name, and the range the reference allows for each.
struct OverrideBound {double low=0.,high=0.;};
const std::map<std::string,OverrideBound>& override_bounds();
// The override that gives a world mountains. Gain on collision uplift in the tectonic
// phase: ocean basins keep the depth the hypsometric profile gives them while orogenic
// belts rise, so peaks come from where plates actually meet rather than from stretching
// the finished terrain. Around ten puts the tallest peak at the deepest ocean floor.
std::map<std::string,double> orogeny_overrides(double gain);
// A world of a given width, with a vertical relief that does not depend on that width.
// Size is carried by the design radius rather than the shared scale, because the scale
// multiplies heights along with distances: a wider world built that way gets taller
// mountains and deeper oceans for free, which is not what a game means by a bigger
// map. Relief is metres of tectonic uplift scale on the finished world; amplitude
// keeps the recipe's own ratio to it.
std::map<std::string,double> world_shape_overrides(double circumference_m,double relief_m,double orogeny);
// The scale that gives a world of this circumference, for a consumer that thinks in
// kilometres rather than in the reference's design radius.
double world_scale_for_circumference(double metres);
// Whole centimetres from an exact integer or decimal-string source offset in metres.
std::int64_t source_centimetres(const json::Value& value);
UnrealPoint unreal_point(const json::Value& value);
std::string unreal_point_json(const UnrealPoint& point);
GenerateRequest generate_request(const json::Value& value);
std::string generate_request_json(const GenerateRequest& request);
}
