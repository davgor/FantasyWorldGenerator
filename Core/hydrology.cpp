#include "hydrology.hpp"
#include <algorithm>
#include <cmath>
#include <queue>
#include <set>
namespace fantasy_world_generator {
std::int64_t SphereGrid::index(std::int64_t x,std::int64_t z) const {
    if(z==0) return 0;
    if(z==n-1) return static_cast<std::int64_t>(points.size())-1;
    return 1+(z-1)*(n-1)+((x%(n-1))+(n-1))%(n-1);
}
SphereGrid sphere_grid(std::int64_t n,double radius) {
    SphereGrid grid;grid.n=n;
    grid.points.emplace_back(0,0);
    for(std::int64_t z=1;z<n-1;++z) for(std::int64_t x=0;x<n-1;++x) grid.points.emplace_back(x,z);
    grid.points.emplace_back(0,n-1);
    std::vector<Vec3> vectors;
    vectors.reserve(grid.points.size());
    for(const auto& point:grid.points) vectors.push_back(direction(point.first,point.second,n));
    const double step=pi/static_cast<double>(n-1);
    for(std::size_t i=0;i<grid.points.size();++i) {
        const std::int64_t x=grid.points[i].first,z=grid.points[i].second;
        const double lat=pi/2-static_cast<double>(z)*step;
        const double area=radius*radius*2*step*(std::sin(std::min(pi/2,lat+step/2))-std::sin(std::max(-pi/2,lat-step/2)));
        grid.areas.push_back(area*((z==0 || z==n-1) ? static_cast<double>(n-1) : 1.));
        std::set<std::int64_t> ids;
        if(z==0 || z==n-1) {
            for(std::int64_t xx=0;xx<n-1;++xx) ids.insert(grid.index(xx,z==0 ? 1 : n-2));
        } else {
            for(std::int64_t dx=-1;dx<=1;++dx) for(std::int64_t dz=-1;dz<=1;++dz) ids.insert(grid.index(x+dx,z+dz));
            ids.erase(static_cast<std::int64_t>(i));
        }
        std::vector<std::pair<std::int64_t,double>> edges;
        for(std::int64_t j:ids)
            edges.emplace_back(j,radius*std::acos(std::max(-1.,std::min(1.,dot(vectors[i],vectors[static_cast<std::size_t>(j)])))));
        grid.neighbors.push_back(edges);
    }
    return grid;
}
Grid node_grid(const std::vector<double>& values,const SphereGrid& sphere) {
    const auto n=static_cast<std::size_t>(sphere.n);
    Grid out=filled(n,0.);
    for(std::size_t i=0;i<sphere.points.size();++i)
        out[static_cast<std::size_t>(sphere.points[i].second)][static_cast<std::size_t>(sphere.points[i].first)]=values[i];
    out[0].assign(n,values.front());
    out[n-1].assign(n,values.back());
    for(auto& row:out) row[n-1]=row[0];
    return out;
}
std::vector<double> node_values(const Grid& grid,const SphereGrid& sphere) {
    std::vector<double> values;
    values.reserve(sphere.points.size());
    for(const auto& point:sphere.points)
        values.push_back(grid[static_cast<std::size_t>(point.second)][static_cast<std::size_t>(point.first)]);
    return values;
}
SedimentBudget erode(const Grid& height,double radius,double sea_level,std::int64_t passes,double strength,
                     const SphereGrid& grid,Layers& layers) {
    (void)radius;
    const std::size_t count=grid.points.size();
    std::vector<double> h=node_values(height,grid),original=h;
    const double ceiling=*std::max_element(h.begin(),h.end());
    std::vector<double> sediment(count,0.),cut(count,0.),fill(count,0.),flow=grid.areas;
    double total_cut=0.,total_fill=0.;
    std::vector<double> slopes(count,0.);
    std::vector<std::int64_t> receiver(count,-1);
    std::vector<std::size_t> order(count);
    auto routes=[&]() {
        for(std::size_t i=0;i<count;++i) {
            double best_slope=0.;std::int64_t best=-1;
            if(h[i]>sea_level) {
                for(const auto& edge:grid.neighbors[i]) {
                    const auto j=static_cast<std::size_t>(edge.first);
                    if(!(h[j]<h[i] && edge.second>0)) continue;
                    const double slope=(h[i]-h[j])/edge.second;
                    // max() over (slope, node, distance) tuples keeps the reference tie order.
                    if(best<0 || slope>best_slope || (slope==best_slope && edge.first>best)) {
                        best_slope=slope;best=edge.first;
                    }
                }
            }
            slopes[i]=best<0 ? 0. : best_slope;
            receiver[i]=best;
        }
        for(std::size_t i=0;i<count;++i) order[i]=i;
        std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {return h[a]>h[b];});
        flow=grid.areas;
        for(std::size_t k=0;k<count;++k) {
            const std::size_t i=order[k];
            if(receiver[i]>=0) flow[static_cast<std::size_t>(receiver[i])]+=flow[i];
        }
    };
    for(std::int64_t pass=0;pass<passes;++pass) {
        routes();
        std::vector<double> delta(count,0.),retained(count,0.);
        for(std::size_t k=0;k<count;++k) {
            const std::size_t i=order[k];
            const std::int64_t j=receiver[i];
            // Stream-power proxy, limited to a fraction of the downstream drop.
            const double drop=j>=0 ? std::min(.15*(h[i]-h[static_cast<std::size_t>(j)]),
                                              strength*.04*std::sqrt(flow[i])*slopes[i]) : 0.;
            const double capacity=2*drop*grid.areas[i];
            const double incoming=sediment[i];
            const double removed=std::min(drop*grid.areas[i],std::max(0.,capacity-incoming));
            const double load=incoming+removed;
            const double deposited=std::min(std::max(0.,load-capacity),std::max(0.,ceiling-h[i])*.25*grid.areas[i]);
            delta[i]+=(deposited-removed)/grid.areas[i];
            cut[i]+=removed/grid.areas[i];fill[i]+=deposited/grid.areas[i];
            total_cut+=removed;total_fill+=deposited;
            if(j>=0) sediment[static_cast<std::size_t>(j)]+=load-deposited;
            else retained[i]=load-deposited;
        }
        for(std::size_t i=0;i<count;++i) h[i]+=delta[i];
        sediment=retained;
    }
    // Diagnostics describe the final surface, not the preceding iteration.
    routes();
    std::vector<double> change(count,0.);
    for(std::size_t i=0;i<count;++i) change[i]=h[i]-original[i];
    layers.height=node_grid(h,grid);
    layers.erosion=node_grid(cut,grid);
    layers.deposition=node_grid(fill,grid);
    layers.erosion_delta=node_grid(change,grid);
    layers.catchment=node_grid(flow,grid);
    SedimentBudget budget;
    budget.eroded_m3=total_cut;budget.deposited_m3=total_fill;
    Sum stored;
    for(double value:sediment) stored.add(value);
    budget.stored_sediment_m3=stored.value();
    budget.balance_error_m3=total_cut-total_fill-budget.stored_sediment_m3;
    return budget;
}
namespace {
WaterRouting route_water(const std::vector<double>& h,const std::vector<double>& areas,
                         const SphereGrid& grid,double sea) {
    const std::size_t count=h.size();
    std::set<std::size_t> remaining;
    for(std::size_t i=0;i<count;++i) if(h[i]<=sea) remaining.insert(i);
    std::vector<std::vector<std::size_t>> components;
    while(!remaining.empty()) {
        const std::size_t start=*remaining.begin();
        remaining.erase(remaining.begin());
        std::vector<std::size_t> group{start},stack{start};
        while(!stack.empty()) {
            const std::size_t i=stack.back();stack.pop_back();
            for(const auto& edge:grid.neighbors[i]) {
                const auto j=static_cast<std::size_t>(edge.first);
                if(remaining.erase(j)) {group.push_back(j);stack.push_back(j);}
            }
        }
        components.push_back(group);
    }
    std::vector<std::size_t> ocean_ids;
    double best_area=-1.;
    for(const auto& group:components) {
        Sum area;
        for(std::size_t i:group) area.add(areas[i]);
        if(area.value()>best_area) {best_area=area.value();ocean_ids=group;}
    }
    WaterRouting routed;
    routed.ocean.assign(count,false);
    for(std::size_t i:ocean_ids) routed.ocean[i]=true;
    routed.has_ocean=!ocean_ids.empty();
    std::vector<std::size_t> roots=ocean_ids;
    if(roots.empty()) {
        std::size_t lowest=0;
        for(std::size_t i=1;i<count;++i) if(h[i]<h[lowest]) lowest=i;
        roots.push_back(lowest);
    }
    std::set<std::size_t> root_set(roots.begin(),roots.end());
    routed.level=h;
    routed.receivers.assign(count,-1);
    std::vector<bool> visited(count,false);
    using Entry=std::pair<double,std::size_t>;
    std::priority_queue<Entry,std::vector<Entry>,std::greater<Entry>> queue;
    for(std::size_t i:roots) {
        visited[i]=true;
        routed.level[i]=routed.ocean[i] ? sea : h[i];
        queue.emplace(routed.level[i],i);
    }
    std::vector<std::size_t> order;
    std::vector<std::size_t> rank(count,0);
    while(!queue.empty()) {
        const auto entry=queue.top();queue.pop();
        const std::size_t i=entry.second;
        rank[i]=order.size();order.push_back(i);
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            if(visited[j]) continue;
            visited[j]=true;
            routed.receivers[j]=static_cast<std::int64_t>(i);
            routed.level[j]=std::max(h[j],entry.first);
            queue.emplace(routed.level[j],j);
        }
    }
    // Steepest descent on the spill surface where possible; flood parents route flats.
    for(std::size_t i:order) {
        if(root_set.count(i)) continue;
        double best_slope=0.;std::int64_t best=-1;
        for(const auto& edge:grid.neighbors[i]) {
            const auto j=static_cast<std::size_t>(edge.first);
            if(!(edge.second>0 && routed.level[j]<routed.level[i] && rank[j]<rank[i])) continue;
            const double slope=(routed.level[i]-routed.level[j])/edge.second;
            if(best<0 || slope>best_slope || (slope==best_slope && edge.first>best)) {best_slope=slope;best=edge.first;}
        }
        if(best>=0) routed.receivers[i]=best;
    }
    routed.flow=areas;
    for(auto it=order.rbegin();it!=order.rend();++it)
        if(routed.receivers[*it]>=0) routed.flow[static_cast<std::size_t>(routed.receivers[*it])]+=routed.flow[*it];
    return routed;
}
}
WaterRouting add_water(const WorldConfig& cfg,double sea_level,const SphereGrid& grid,Layers& layers) {
    const std::vector<double> h=node_values(layers.height,grid);
    WaterRouting routed=route_water(h,grid.areas,grid,sea_level);
    const std::size_t count=h.size();
    std::vector<double> depth(count,0.),kind(count,0.),river(count,0.);
    for(std::size_t i=0;i<count;++i) {
        depth[i]=std::max(0.,routed.level[i]-h[i]);
        kind[i]=routed.ocean[i] ? 1. : (depth[i]>1e-7 ? 2. : 0.);
    }
    // Uniform unit runoff proxy, not rainfall volume. River width is not modelled.
    for(std::size_t i=0;i<count;++i)
        river[i]=(kind[i]==0. && routed.receivers[i]>=0 && routed.flow[i]>=cfg.river_threshold_km2*1e6) ? 1. : 0.;
    layers.water_type=node_grid(kind,grid);
    layers.water_depth=node_grid(depth,grid);
    layers.water_surface=node_grid(routed.level,grid);
    layers.routed_catchment=node_grid(routed.flow,grid);
    layers.river=node_grid(river,grid);
    return routed;
}
}
