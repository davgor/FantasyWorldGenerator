#pragma once
#include "json.hpp"
namespace fantasy_world_generator {
// Request boundary for world genesis. No Unreal, engine, asset or Python dependency:
// Unreal centimetres are plain integers here and a future adapter owns engine types.
constexpr std::int64_t genesis_recipe=3, max_seed=4294967295LL, min_grid=1, max_grid=257,
                      centimetres_per_metre=100, max_metres=max_safe/centimetres_per_metre;
constexpr std::size_t max_offset_text=24;
// Unreal is left-handed and Z-up: source east is X, source north is Y, source up is Z.
struct UnrealPoint { std::int64_t x_cm=0, y_cm=0, z_cm=0; };
struct GenerateRequest {
    std::int64_t recipe_version=genesis_recipe, seed=0;
    std::optional<std::int64_t> size;
    std::optional<std::string> shape;
};
// Whole centimetres from an exact integer or decimal-string source offset in metres.
std::int64_t source_centimetres(const json::Value& value);
UnrealPoint unreal_point(const json::Value& value);
std::string unreal_point_json(const UnrealPoint& point);
GenerateRequest generate_request(const json::Value& value);
std::string generate_request_json(const GenerateRequest& request);
}
