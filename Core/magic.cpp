#include "magic.hpp"
#include "json.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <set>
namespace fantasy_world_generator {
namespace {
Vec3 normalized(const Vec3& q) {
    // The reference normalizes with a compensated sum, like every other length here.
    Sum squares;
    for(double value:q) squares.add(value*value);
    const double length=std::sqrt(squares.value());
    return Vec3{q[0]/length,q[1]/length,q[2]/length};
}
Vec3 random_unit(PyRandom& rng) {
    const double y=rng.uniform(-1,1);
    const double a=rng.uniform(-pi,pi);
    const double r=std::sqrt(1-y*y);
    return Vec3{r*std::cos(a),y,r*std::sin(a)};
}
struct SchoolOption {double occurrence,strength,width,instability;std::int64_t nodes,variation;};
SchoolOption school_option(const WorldConfig& cfg,std::size_t index) {
    // terrain_world.OPTIONS defaults: umbral and infernal are weaker, infernal is the
    // unstable one, and every school shares the remaining values.
    const std::string name=school_names()[index];
    SchoolOption option{1.,.7,110.,.2,8,0};
    (void)cfg;
    if(name=="umbral" || name=="infernal") option.strength=.45;
    if(name=="infernal") option.instability=.65;
    return option;
}
}
const std::array<const char*,school_count>& school_names() {
    static const std::array<const char*,school_count> names{
        "weave","umbral","infernal","radiant","fire","water","earth","air"};
    return names;
}
ArcFrame arc_frame(const Vec3& a,const Vec3& b) {
    const double cosine=std::max(-1.,std::min(1.,dot(a,b)));
    const double angle=std::acos(cosine);
    Vec3 tangent{};
    for(int i=0;i<3;++i) tangent[i]=(b[i]-cosine*a[i])/std::max(1e-12,std::sin(angle));
    return ArcFrame{a,b,tangent,angle};
}
double distance_to_frame(const Vec3& p,const ArcFrame& frame) {
    const double pa=dot(p,frame.start),pt=dot(p,frame.tangent);
    const double along=std::atan2(pt,pa);
    double best=std::max(pa,dot(p,frame.end));
    if(along>=0 && along<=frame.angle) best=std::max(best,python_hypot(pa,pt));
    return std::acos(std::max(-1.,std::min(1.,best)));
}
void network_geometry(std::uint32_t seed,std::int64_t count,std::vector<Vec3>& nodes,
                      std::vector<std::pair<std::size_t,std::size_t>>& pairs) {
    PyRandom rng(child_seed(seed,"clustered-ley-v1"));
    nodes.clear();pairs.clear();
    const std::int64_t clusters=rng.randint(1,std::min<std::int64_t>(4,count));
    std::vector<Vec3> centres;
    for(std::int64_t i=0;i<clusters;++i) centres.push_back(random_unit(rng));
    const double spread=rng.uniform(.12,.8),outlier=rng.uniform(.05,.4);
    std::vector<std::int64_t> groups;
    for(std::int64_t i=0;i<count;++i) {
        const auto group=static_cast<std::size_t>(rng.randrange(0,clusters));
        Vec3 p{};
        bool separated=false;
        for(int attempt=0;attempt<1000;++attempt) {
            if(rng.next()<outlier) p=random_unit(rng);
            else {
                Vec3 q{};
                for(int j=0;j<3;++j) q[j]=centres[group][j]+rng.gauss(0,spread);
                p=normalized(q);
            }
            separated=true;
            for(const Vec3& other:nodes) if(!(std::fabs(dot(p,other))<.9999)) {separated=false;break;}
            if(separated) break;
        }
        if(!separated) throw Error("STATE_CAPACITY");
        nodes.push_back(p);
        groups.push_back(static_cast<std::int64_t>(group));
    }
    // Three sacred loci share a straight spherical alignment; the rest stay scattered.
    // A fantasy reading of Watkins' alignments, not a physical law.
    std::set<std::pair<std::size_t,std::size_t>> linked;
    if(count>=3) {
        const ArcFrame arc=arc_frame(nodes[0],nodes[1]);
        const double t=rng.uniform(.3,.7)*arc.angle;
        for(int i=0;i<3;++i) nodes[2][i]=arc.start[i]*std::cos(t)+arc.tangent[i]*std::sin(t);
        groups[1]=groups[2]=groups[0];
        linked.insert({0,2});
        linked.insert({1,2});
    }
    // Sparse trees within clusters; some schools stay in disconnected concentrations.
    for(std::int64_t group=0;group<clusters;++group) {
        std::vector<std::size_t> members;
        for(std::size_t i=0;i<groups.size();++i) if(groups[i]==group) members.push_back(i);
        if(members.empty()) continue;
        std::set<std::size_t> joined{members.front()};
        while(joined.size()<members.size()) {
            double best=0.;std::size_t from=0,to=0;bool found=false;
            for(std::size_t a:joined) {
                for(std::size_t b:members) {
                    if(joined.count(b)) continue;
                    const double distance=1-dot(nodes[a],nodes[b]);
                    if(!found || distance<best || (distance==best && (a<from || (a==from && b<to)))) {
                        best=distance;from=a;to=b;found=true;
                    }
                }
            }
            if(!found) break;
            linked.insert({std::min(from,to),std::max(from,to)});
            joined.insert(to);
        }
    }
    const double link_chance=rng.uniform(.08,.45);
    for(std::int64_t a=0;a<count;++a) {
        if(rng.next()<link_chance) {
            const std::size_t pick=rng.choice(static_cast<std::size_t>(count-1));
            const auto b=static_cast<std::size_t>(pick>=static_cast<std::size_t>(a) ? pick+1 : pick);
            const auto first=static_cast<std::size_t>(a);
            linked.insert({std::min(first,b),std::max(first,b)});
        }
    }
    pairs.assign(linked.begin(),linked.end());
}
std::vector<LeyNetwork> generate_networks(const WorldConfig& cfg) {
    std::vector<LeyNetwork> networks;
    for(std::size_t index=0;index<school_count;++index) {
        const SchoolOption option=school_option(cfg,index);
        LeyNetwork network;
        network.name=school_names()[index];
        network.strength=option.strength;
        // Authored school widths are a reach on the reference world (design radius 10000
        // at the recipe scale, 1774.4 m physical), so magic must cover the same share of
        // the world at every circumference. Left absolute, a 110 m Gaussian on a 200 km
        // world falls entirely between raster cells and every ley field, magic density,
        // biome variant, college and magic-gated habitat collapses to zero. This mirrors
        // terrain_leyline_history.py:101; the reference radius is written as the decimal
        // literal the reference uses, because 10000.*0.17744123532462844 evaluates one ulp
        // lower and the categorical layers downstream are compared exactly.
        network.width_m=option.width*(cfg.globe_radius*cfg.world_scale/1774.4123532462844);
        network.instability=option.instability;
        network.seed=child_seed(static_cast<std::uint64_t>(cfg.seed),"history-ley-"+network.name,
                                static_cast<std::uint64_t>(option.variation));
        // One draw from a fresh stream decides manifestation, exactly as the reference does.
        PyRandom occurrence(network.seed);
        network.enabled=cfg.magic_enabled!=0 && occurrence.next()<option.occurrence;
        if(network.enabled) {
            std::vector<Vec3> positions;
            std::vector<std::pair<std::size_t,std::size_t>> links;
            network_geometry(network.seed,option.nodes,positions,links);
            PyRandom rng(child_seed(static_cast<std::uint64_t>(network.seed),"intensities"));
            for(const Vec3& p:positions) network.nodes.push_back(LeyNode{p,rng.uniform(.35,1.65)});
            for(const auto& link:links) network.edges.push_back(LeyEdge{link.first,link.second,rng.uniform(.35,1.65)});
        }
        networks.push_back(network);
    }
    return networks;
}
std::int64_t dominant_school(const std::array<double,school_count>& potency,double threshold,double margin) {
    std::array<std::size_t,school_count> order{};
    for(std::size_t i=0;i<school_count;++i) order[i]=i;
    // Ranked by potency descending, then by school name: the tie rule is part of the
    // contract because a mutation identity depends on it.
    std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
        if(potency[a]!=potency[b]) return potency[a]>potency[b];
        return std::string(school_names()[a])<std::string(school_names()[b]);
    });
    const double winner=potency[order[0]],runner=potency[order[1]];
    if(winner>=threshold && winner-runner>=margin) return static_cast<std::int64_t>(order[0]);
    return -1;
}
void evaluate_networks(const WorldConfig& cfg,double radius,const SphereGrid& grid,
                       const std::vector<LeyNetwork>& networks,Layers& layers) {
    const std::size_t count=grid.points.size();
    std::vector<Vec3> vectors;
    vectors.reserve(count);
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,cfg.size));
    std::array<std::vector<double>,school_count> power{},unstable{};
    for(std::size_t index=0;index<school_count;++index) {
        const LeyNetwork& net=networks[index];
        std::vector<ArcFrame> frames;
        frames.reserve(net.edges.size());
        for(const LeyEdge& edge:net.edges)
            frames.push_back(arc_frame(net.nodes[edge.from].direction,net.nodes[edge.to].direction));
        power[index].reserve(count);
        unstable[index].reserve(count);
        for(const Vec3& p:vectors) {
            Sum nodes_total;
            for(const LeyNode& node:net.nodes) {
                const double arc=radius*std::acos(std::max(-1.,std::min(1.,dot(p,node.direction))));
                nodes_total.add(node.intensity*std::exp(-std::pow(arc/net.width_m,2.)));
            }
            Sum edges_total;
            for(std::size_t e=0;e<net.edges.size();++e) {
                const LeyEdge& edge=net.edges[e];
                const double pair=(net.nodes[edge.from].intensity+net.nodes[edge.to].intensity)/2;
                const double reach=radius*distance_to_frame(p,frames[e]);
                edges_total.add(edge.intensity*pair*std::exp(-std::pow(reach/net.width_m,2.)));
            }
            const double total=nodes_total.value()+edges_total.value();
            const double value=net.strength*-std::expm1(-total);
            power[index].push_back(value);
            unstable[index].push_back(std::min(1.,value*net.instability));
        }
    }
    for(std::size_t index=0;index<school_count;++index) {
        layers.ley[index]=node_grid(power[index],grid);
        layers.instability[index]=node_grid(unstable[index],grid);
    }
    std::vector<double> density,hazard,growth,opposition,winners,primordial;
    for(std::size_t i=0;i<count;++i) {
        std::array<double,school_count> potency{};
        Sum total;
        for(std::size_t index=0;index<school_count;++index) {
            potency[index]=power[index][i];
            total.add(potency[index]);
        }
        const double weave=potency[0],umbral=potency[1],infernal=potency[2],radiant=potency[3];
        const double fire=potency[4],water=potency[5],earth=potency[6],air=potency[7];
        const double conflict=std::min(radiant,infernal)+std::min(weave,umbral)+std::min(fire,water);
        Sum instability_total;
        for(std::size_t index=0;index<school_count;++index) instability_total.add(unstable[index][i]);
        density.push_back(-std::expm1(-total.value()));
        opposition.push_back(std::min(1.,conflict));
        hazard.push_back(std::min(1.,instability_total.value()*.3+conflict*.2));
        growth.push_back((earth+.6*radiant+.5*weave+.4*water)/std::max(total.value(),1e-12));
        winners.push_back(static_cast<double>(dominant_school(potency)));
        primordial.push_back(std::max(std::max(fire,water),std::max(earth,air)));
    }
    layers.magic_density=node_grid(density,grid);
    layers.magic_hazard=node_grid(hazard,grid);
    layers.magic_growth=node_grid(growth,grid);
    layers.magic_opposition=node_grid(opposition,grid);
    layers.dominant_magic=node_grid(winners,grid);
    // Compatibility projections the ecology and nest rules already expect; never extra
    // networks, just named views of the eight.
    layers.ley_holy=layers.ley[3];
    layers.ley_primordial=node_grid(primordial,grid);
}
}
