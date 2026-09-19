#include "registry.hpp"
namespace fantasy_world_generator {
namespace {
using json::Value;
void require(bool ok) {if(!ok) throw Error("INVALID_INPUT");}
bool object_path(const std::string& path) {
    // Engine object paths only: no relative escapes and no empty package names.
    if(path.size()<3 || path.size()>json::max_text_bytes || path[0]!='/') return false;
    if(path.find("..")!=std::string::npos || path.find("//")!=std::string::npos) return false;
    return path.find('.')!=std::string::npos;
}
}
AssetRegistry AssetRegistry::parse(const std::string& text) {
    const Value document=json::parse(text);
    if(json::string(json::field(document,"schema"))!="fantasy-world-generator.unreal-asset-registry")
        throw Error("UNSUPPORTED_VERSION");
    if(json::integer(json::field(document,"version"))!=asset_registry_version) throw Error("UNSUPPORTED_VERSION");
    AssetRegistry registry;
    registry.recipe_version_=json::integer(json::field(document,"recipe_version"));
    registry.asset_list_sha256_=json::string(json::field(document,"asset_list_sha256"));
    require(registry.asset_list_sha256_.size()==64);
    const auto& rows=json::array(json::field(document,"rows"));
    require(!rows.empty());
    for(const auto& row:rows) {
        AssetBinding binding;
        binding.id=json::string(json::field(row,"id"));
        binding.kind=json::string(json::field(row,"kind"));
        binding.status=json::string(json::field(row,"status"));
        require(!binding.id.empty() && !binding.kind.empty());
        if(binding.status=="bound" || binding.status=="placeholder") {
            binding.path=json::string(json::field(row,"path"));
            require(object_path(binding.path));
        } else if(binding.status=="unbound") {
            binding.reason=json::string(json::field(row,"reason"));
            require(!binding.reason.empty());
        } else {
            throw Error("INVALID_INPUT");
        }
        // Registry identities are unique: a second row would make resolution ambiguous.
        require(registry.index_.emplace(binding.id,registry.order_.size()).second);
        registry.order_.push_back(binding);
    }
    return registry;
}
const AssetBinding* AssetRegistry::find(const std::string& id) const {
    const auto found=index_.find(id);
    return found==index_.end() ? nullptr : &order_[found->second];
}
std::vector<std::string> AssetRegistry::unbound() const {
    std::vector<std::string> names;
    for(const auto& binding:order_) if(!binding.bound()) names.push_back(binding.id);
    return names;
}
}
