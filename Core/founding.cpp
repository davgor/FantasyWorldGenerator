#include "founding.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <set>
namespace fantasy_world_generator {
namespace {
struct Candidate {std::string civilization;std::size_t node=0;};
}
FoundingResult found_cities(std::uint32_t seed,const WorldConfig& cfg,double radius,const SphereGrid& grid,
                            const Catalogues& catalogues,const SettlementFields& fields,
                            const FoundingContext& context) {
    const std::vector<std::string>& civilizations=catalogues.civilization_ids();
    const FoundingRules& rules=catalogues.founding_rules();
    const double spacing=cfg.settlement_spacing;
    const double world_reach=pi*radius;
    std::vector<Vec3> vectors;
    vectors.reserve(grid.points.size());
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,cfg.size));
    auto separation=[&](std::size_t a,std::size_t b) {
        return radius*std::acos(std::max(-1.,std::min(1.,dot(vectors[a],vectors[b]))));
    };
    // Only the parent races that actually own a civilization take turns.
    std::vector<ParentRace> races;
    for(const ParentRace& race:catalogues.parent_races()) {
        for(const std::string& civilization:civilizations)
            if(catalogues.parent_race_id(civilization)==race.id) {races.push_back(race);break;}
    }
    FoundingResult result;
    std::map<std::string,std::int64_t> quotas;
    for(const std::string& civilization:civilizations) {
        const std::int64_t minimum=static_cast<std::int64_t>(
            catalogues.profile(civilization).trait("minimum_founding_residents"));
        const std::int64_t allowance=fields.budget.allowances.at(civilization);
        quotas[civilization]=std::min(fields.budget.quotas.at(civilization),
                                      minimum>0 ? allowance/minimum : 0);
    }
    // The ceiling actually in force, which the budget has already resolved: the
    // ground's packing, the caller's count, or a real zero for an empty world.
    const std::int64_t ceiling=fields.budget.city_limit;
    const double origin_gap=world_reach*rules.origin_min_separation_degrees/180;
    std::int64_t target=0;
    for(const auto& entry:quotas) target+=entry.second;
    const double base=std::max(std::max(spacing*2,world_reach/32),1.);
    // A later age starts from the cities that survived, and never rebuilds on a ruin.
    result.sites=context.survivors;
    const std::set<std::size_t> forbidden(context.forbidden.begin(),context.forbidden.end());
    std::set<std::string> ever_used(context.used_civilizations.begin(),context.used_civilizations.end());
    std::set<std::string> bonus_used(context.bonus_used.begin(),context.bonus_used.end()),blocked_parents;
    for(const FoundedCity& site:result.sites) ever_used.insert(site.population_profile);
    double year_offset=context.start_year;
    if(!result.sites.empty()) {
        double latest=0.;
        for(const FoundedCity& site:result.sites) latest=std::max(latest,site.founding_year);
        year_offset=std::max(year_offset,latest+rules.years_per_round);
    }
    auto spaced=[&](std::size_t node) {
        if(forbidden.count(node)!=0) return false;
        for(const FoundedCity& site:result.sites)
            if(node==site.node || !(separation(node,site.node)>=spacing)) return false;
        return true;
    };
    // Cities are only ever added inside a round, so a candidate that has lost its
    // spacing can never regain it. Keeping a shrinking list of still-viable nodes per
    // people turns a rescan of every candidate against every city, on every turn, into
    // one pass per city. The list keeps candidate order, so the choice is unchanged:
    // on a world with hundreds of cities this is the difference between founding
    // taking seconds and taking milliseconds.
    std::map<std::string,std::vector<std::size_t>> viable;
    for(const std::string& civilization:civilizations) {
        std::vector<std::size_t> nodes;
        for(std::size_t node:fields.species.at(civilization).candidates)
            if(spaced(node)) nodes.push_back(node);
        viable.emplace(civilization,std::move(nodes));
    }
    auto retire=[&](std::size_t placed) {
        for(auto& entry:viable) {
            std::vector<std::size_t>& nodes=entry.second;
            nodes.erase(std::remove_if(nodes.begin(),nodes.end(),[&](std::size_t node) {
                return node==placed || !(separation(node,placed)>=spacing);
            }),nodes.end());
        }
    };
    auto available=[&](const std::string& race) {
        std::vector<Candidate> pool;
        for(const std::string& civilization:civilizations) {
            if(catalogues.parent_race_id(civilization)!=race) continue;
            std::int64_t placed=0;
            for(const FoundedCity& site:result.sites) placed+=site.population_profile==civilization ? 1 : 0;
            if(placed>=quotas.at(civilization)) continue;
            for(std::size_t node:viable.at(civilization)) pool.push_back(Candidate{civilization,node});
        }
        return pool;
    };
    auto best_candidate=[&](const std::vector<Candidate>& pool) {
        const Candidate* best=nullptr;
        for(const Candidate& option:pool) {
            if(best==nullptr) {best=&option;continue;}
            const double score=fields.species.at(option.civilization).suitability[option.node];
            const double incumbent=fields.species.at(best->civilization).suitability[best->node];
            if(score>incumbent) {best=&option;continue;}
            if(score<incumbent) continue;
            if(option.civilization<best->civilization) {best=&option;continue;}
            if(option.civilization==best->civilization && option.node<best->node) best=&option;
        }
        return best;
    };
    auto nearest_member=[&](const std::string& race,std::size_t node,const FoundedCity*& source) {
        source=nullptr;
        double best=0.;
        for(const FoundedCity& site:result.sites) {
            if(site.parent_race_id!=race) continue;
            const double distance=separation(node,site.node);
            if(source==nullptr || distance<best || (distance==best && site.node<source->node)) {
                best=distance;source=&site;
            }
        }
    };
    std::string stop="round_limit_reached";
    std::int64_t turn=1;
    for(;turn<=128;++turn) {
        const double search=std::min(world_reach,base*std::pow(1.6,static_cast<double>(std::min<std::int64_t>(turn-1,32))));
        bool possible=false;
        // Rotate initiative so one parent never claims every contested site first.
        std::vector<ParentRace> order=races;
        if(!order.empty()) {
            const std::size_t offset=static_cast<std::size_t>((turn-1)%static_cast<std::int64_t>(order.size()));
            std::rotate(order.begin(),order.begin()+static_cast<std::ptrdiff_t>(offset),order.end());
        }
        for(const ParentRace& race:order) {
            if(static_cast<std::int64_t>(result.sites.size())>=target) break;
            if(blocked_parents.count(race.id)) continue;
            bool has_members=false;
            for(const FoundedCity& site:result.sites) if(site.parent_race_id==race.id) {has_members=true;break;}
            std::vector<Candidate> pool=available(race.id);
            if(pool.empty() || ((turn>1 || has_members) && race.founding_participation_percent==0)) continue;
            if(!has_members) {
                // A first city has to stand clear of every other parent's origin.
                std::vector<Candidate> separated;
                for(const Candidate& option:pool) {
                    bool clear=true;
                    for(const FoundedCity& site:result.sites) {
                        if(!site.founding_capital) continue;
                        if(!(separation(option.node,site.node)+1e-8>=origin_gap)) {clear=false;break;}
                    }
                    if(clear) separated.push_back(option);
                }
                pool=separated;
                if(pool.empty()) {blocked_parents.insert(race.id);continue;}
            }
            possible=true;
            PyRandom rng(child_seed(seed,"founding-"+std::to_string(turn)+"-"+race.id));
            const double draw=rng.next()*100;
            if((turn>1 || has_members) && draw>=race.founding_participation_percent) continue;
            std::vector<Candidate> unused;
            for(const Candidate& option:pool) {
                bool taken=false;
                for(const FoundedCity& site:result.sites)
                    if(site.population_profile==option.civilization) {taken=true;break;}
                if(!taken) unused.push_back(option);
            }
            if(!unused.empty()) pool=unused;
            if(has_members) {
                std::vector<Candidate> reachable;
                for(const Candidate& option:pool) {
                    double nearest=0.;
                    bool first=true;
                    for(const FoundedCity& site:result.sites) {
                        if(site.parent_race_id!=race.id) continue;
                        const double distance=separation(option.node,site.node);
                        if(first || distance<nearest) {nearest=distance;first=false;}
                    }
                    if(!first && nearest<=search) reachable.push_back(option);
                }
                pool=reachable;
            }
            if(pool.empty()) continue;
            const Candidate* chosen=best_candidate(pool);
            const FoundedCity* source=nullptr;
            if(has_members) nearest_member(race.id,chosen->node,source);
            FoundedCity city;
            city.node=chosen->node;
            city.population_profile=chosen->civilization;
            city.parent_race_id=race.id;
            city.founding_turn=turn;
            city.founding_capital=!has_members;
            city.founding_year=year_offset+static_cast<double>(turn-1)*rules.years_per_round;
            if(source!=nullptr) {
                city.has_source=true;
                city.migration_source_node=source->node;
                city.source_civilization_id=source->population_profile;
                city.migration_distance_m=separation(chosen->node,source->node);
                city.cultural_branch=source->population_profile!=chosen->civilization;
            }
            result.sites.push_back(city);
            retire(city.node);
            ever_used.insert(chosen->civilization);
        }
        const double year=year_offset+static_cast<double>(turn-1)*rules.years_per_round;
        // A diaspora can seat an unused civilization that the quotas never reached.
        auto diaspora_options=[&]() {
            std::map<std::string,std::vector<std::size_t>> options;
            if(static_cast<std::int64_t>(result.sites.size())>=ceiling) return options;
            for(const std::string& civilization:civilizations) {
                const std::int64_t minimum=static_cast<std::int64_t>(
                    catalogues.profile(civilization).trait("minimum_founding_residents"));
                if(ever_used.count(civilization)) continue;
                if(fields.budget.allowances.at(civilization)<minimum) continue;
                const std::string& race=catalogues.parent_race_id(civilization);
                const bool bonus=quotas.at(civilization)==0;
                if(bonus && (rules.diaspora_bonus_per_parent==0 || bonus_used.count(race)
                             || target>=ceiling)) continue;
                if(static_cast<std::int64_t>(result.sites.size())>=target && !bonus) continue;
                bool has_members=false;
                for(const FoundedCity& site:result.sites) if(site.parent_race_id==race) {has_members=true;break;}
                std::vector<std::size_t> pool;
                for(std::size_t node:viable.at(civilization)) {
                    if(!has_members) {
                        bool clear=true;
                        for(const FoundedCity& site:result.sites) {
                            if(!site.founding_capital) continue;
                            if(!(separation(node,site.node)+1e-8>=origin_gap)) {clear=false;break;}
                        }
                        if(!clear) continue;
                    }
                    pool.push_back(node);
                }
                if(!pool.empty()) options.emplace(civilization,pool);
            }
            return options;
        };
        std::map<std::string,std::vector<std::size_t>> options=diaspora_options();
        if(!options.empty() && year>0 && std::fmod(year,rules.diaspora_interval_years)==0) {
            PyRandom rng(child_seed(seed,"diaspora-"+std::to_string(static_cast<std::int64_t>(year))));
            std::vector<std::string> keys;
            for(const auto& entry:options) keys.push_back(entry.first);
            const std::string civilization=keys[rng.choice(keys.size())];
            const std::string& race=catalogues.parent_race_id(civilization);
            std::size_t node=options.at(civilization).front();
            for(std::size_t option:options.at(civilization)) {
                const double score=fields.species.at(civilization).suitability[option];
                const double incumbent=fields.species.at(civilization).suitability[node];
                if(score>incumbent || (score==incumbent && option<node)) node=option;
            }
            const FoundedCity* source=nullptr;
            nearest_member(race,node,source);
            const bool bonus=quotas.at(civilization)==0;
            if(bonus) {quotas.at(civilization)=1;target+=1;bonus_used.insert(race);}
            FoundedCity city;
            city.node=node;
            city.population_profile=civilization;
            city.parent_race_id=race;
            city.founding_turn=turn;
            city.founding_capital=source==nullptr;
            city.founding_year=year;
            city.diaspora=true;
            city.diaspora_bonus=bonus;
            if(source!=nullptr) {
                city.has_source=true;
                city.migration_source_node=source->node;
                city.source_civilization_id=source->population_profile;
                city.migration_distance_m=separation(node,source->node);
                city.cultural_branch=true;
            }
            static const char* reasons[4]={"exile","religious_schism","expedition","magical_displacement"};
            const std::size_t choices=cfg.magic_enabled ? 4 : 3;
            city.diaspora_reason=reasons[rng.choice(choices)];
            result.sites.push_back(city);
            retire(city.node);
            ever_used.insert(civilization);
            options=diaspora_options();
        }
        if(!options.empty()) possible=true;
        if(static_cast<std::int64_t>(result.sites.size())>=target && options.empty()) {
            stop="capacity_target_reached";break;
        }
        if(!possible) {stop="no_eligible_expansion";break;}
    }
    result.turns=std::min<std::int64_t>(turn,128);
    result.target_cities=target;
    result.effective_quotas=quotas;
    result.stop_reason=stop;
    result.diaspora_bonus_used.assign(bonus_used.begin(),bonus_used.end());
    result.used_civilizations.assign(ever_used.begin(),ever_used.end());
    result.start_year=year_offset;
    result.end_year=year_offset+static_cast<double>(result.turns-1)*rules.years_per_round;
    return result;
}
}
