#pragma once
#include "json.hpp"
#include <map>
#include <string>
#include <vector>
namespace fantasy_world_generator {
constexpr std::int64_t asset_registry_version=1;
// One binding slot per exhaustive-catalogue identity. A row either names an engine
// object path or records an explicit unbound reason; nothing resolves to an
// anonymous mesh, so a missing binding is a diagnostic rather than a silent cube.
struct AssetBinding {
    std::string id,kind,status,path,reason;
    bool bound() const {return status=="bound" || status=="placeholder";}
};
class AssetRegistry {
public:
    static AssetRegistry parse(const std::string& text);
    const AssetBinding* find(const std::string& id) const;
    std::size_t size() const {return order_.size();}
    const std::vector<AssetBinding>& rows() const {return order_;}
    const std::string& asset_list_sha256() const {return asset_list_sha256_;}
    std::int64_t recipe_version() const {return recipe_version_;}
    // Identities with no engine object path, reported so a consumer can surface them.
    std::vector<std::string> unbound() const;
private:
    std::vector<AssetBinding> order_;
    std::map<std::string,std::size_t> index_;
    std::string asset_list_sha256_;
    std::int64_t recipe_version_=0;
};
}
