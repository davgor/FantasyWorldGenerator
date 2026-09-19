#include "scenebuildings.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <cmath>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::scenebuildings {
namespace {

// math.radians multiplies by a compile-time pi/180; it does not divide, so the constant
// has to be formed the same way or the last bit of every rotation moves.
constexpr double deg_to_rad=pi/180.0;
double py_radians(double degrees) {return degrees*deg_to_rad;}

Value vint(std::int64_t value) {return Value::make_int(value);}
Value vflt(double value) {return Value::make_float(value);}
Value vstr(std::string value) {return Value::make_string(std::move(value));}
Value varr() {return Value::make_array();}
Value vobj() {return Value::make_object();}

double as_number(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole_fits?static_cast<double>(value.whole):value.number;
    if(value.kind==Value::Kind::Float) return value.number;
    if(value.kind==Value::Kind::Bool) return value.boolean?1.:0.;
    throw SceneError("Expected a numeric value");
}
std::int64_t as_index(const Value& value) {
    if(value.kind==Value::Kind::Int&&value.whole_fits) return value.whole;
    if(value.kind==Value::Kind::Bool) return value.boolean?1:0;
    // `road['nodes'][lo:hi]` needs an integer bound; Python refuses a float slice too.
    throw SceneError("slice indices must be integers or None or have an __index__ method");
}
const Value* find_field(const Value& owner,const std::string& key) {
    return owner.is_object()?owner.find(key):nullptr;
}
// `str(value)` / `f"{value}"` on the identities this module interpolates.
std::string py_str(const Value& value) {
    switch(value.kind) {
        case Value::Kind::String: return value.text;
        case Value::Kind::Int: return value.whole_fits?std::to_string(value.whole):value.text;
        case Value::Kind::Float: return settlementpresets::py_repr(value.number);
        case Value::Kind::Bool: return value.boolean?"True":"False";
        default: return "None";
    }
}
// Python's `==`, which crosses the int/float line and never crosses the str line.
bool value_equal(const Value& a,const Value& b) {
    const bool a_num=a.is_number()||a.kind==Value::Kind::Bool;
    const bool b_num=b.is_number()||b.kind==Value::Kind::Bool;
    if(a_num&&b_num) {
        if(a.kind==Value::Kind::Int&&b.kind==Value::Kind::Int&&a.whole_fits&&b.whole_fits)
            return a.whole==b.whole;
        return as_number(a)==as_number(b);
    }
    if(a.kind!=b.kind) return false;
    switch(a.kind) {
        case Value::Kind::Null: return true;
        case Value::Kind::String: return a.text==b.text;
        case Value::Kind::Array: {
            if(a.items.size()!=b.items.size()) return false;
            for(std::size_t i=0;i<a.items.size();++i)
                if(!value_equal(a.items[i],b.items[i])) return false;
            return true;
        }
        case Value::Kind::Object: {
            if(a.fields.size()!=b.fields.size()) return false;
            for(const auto& entry:a.fields) {
                const Value* other=b.find(entry.first);
                if(other==nullptr||!value_equal(entry.second,*other)) return false;
            }
            return true;
        }
        default: return false;
    }
}
// `c.get('route_index',-1)>=0`: a number comparison, and a TypeError on anything else.
bool at_least_zero(const Value& value) {
    if(value.is_number()||value.kind==Value::Kind::Bool) return as_number(value)>=0.;
    throw SceneError("'>=' not supported between instances of 'NoneType' and 'int'");
}
// A two-element `[x_m, z_m]` local point, as `local_direction(f,*p)` unpacks it.
void local_point(const Value& point,double& x,double& z) {
    if(!point.is_array()||point.items.size()!=2)
        throw SceneError("local_direction() argument count does not match a 2-element point");
    x=as_number(point.items[0]);
    z=as_number(point.items[1]);
}
// A stored `[x,y,z]` unit direction out of a road connection.
Vec3 as_vector(const Value& value) {
    if(!value.is_array()||value.items.size()!=3)
        throw SceneError("Expected a three-component direction");
    return Vec3{as_number(value.items[0]),as_number(value.items[1]),as_number(value.items[2])};
}
Value from_vector(const Vec3& v) {
    Value out=varr();
    for(int i=0;i<3;++i) out.items.push_back(vflt(v[i]));
    return out;
}
// `points[index]` with Python's list semantics, as sceneframe's own node_at has it.
const std::pair<std::int64_t,std::int64_t>&
node_at(const std::vector<std::pair<std::int64_t,std::int64_t>>& points,std::int64_t index) {
    const std::int64_t count=static_cast<std::int64_t>(points.size());
    const std::int64_t at=index<0?index+count:index;
    if(at<0||at>=count) throw SceneIndexError();
    return points[static_cast<std::size_t>(at)];
}

// ---------------------------------------------------------------------------
// terrain_detail.HeightField, over the raw rasters rather than a world envelope.
//
// DUPLICATED from cityplanner.cpp, where it lives in an anonymous namespace. Kept
// line-for-line with that copy; see the note in scenebuildings.hpp.
// ---------------------------------------------------------------------------
class HeightField {
  public:
    explicit HeightField(const World& world);
    bool defined() const {return defined_;}
    double radius() const {return radius_;}
    double height(const Vec3& p) const;
  private:
    struct Band {double scale,amplitude;std::int64_t seed;};
    static double at(const Grid& h,std::size_t ix,std::size_t iz,std::size_t jz,double fx,double fz) {
        return ((1-fx)*h[iz][ix]+fx*h[iz][ix+1])*(1-fz)+((1-fx)*h[jz][ix]+fx*h[jz][ix+1])*fz;
    }
    void cell(const Vec3& p,std::size_t& ix,std::size_t& iz,std::size_t& jz,
              double& fx,double& fz) const;
    const Grid* base_=nullptr;
    std::int64_t n_=0;
    bool defined_=false;
    Grid strength_,water_;
    double sea_=0.,radius_=0.;
    std::vector<Band> bands_;
};
// `layers.get(key, [[default]*n for _ in range(n)])`.
Grid layer_or(const Layer& layer,std::size_t n,double fallback) {
    if(layer.present) return layer.rows;
    return Grid(n,std::vector<double>(n,fallback));
}
// `{5:1.4,3:.8,4:1.,7:1.,15:.8}.get(code,.65)`: a dict lookup, not arithmetic, so a cell
// that is not a number simply misses every key rather than refusing the world.
double biome_amplitude(const Value& code) {
    if(code.is_number()) {
        const double c=as_number(code);
        if(c==5.) return 1.4;
        if(c==3.) return .8;
        if(c==4.) return 1.;
        if(c==7.) return 1.;
        if(c==15.) return .8;
        return .65;
    }
    if(code.kind==Value::Kind::Array) throw SceneError("unhashable type: 'list'");
    if(code.kind==Value::Kind::Object) throw SceneError("unhashable type: 'dict'");
    return .65;
}
HeightField::HeightField(const World& world) {
    base_=&world.height;
    n_=static_cast<std::int64_t>(world.height.size());
    const auto n=static_cast<std::size_t>(n_);
    defined_=world.has_terrain_detail;
    radius_=world.globe_radius;
    sea_=world.sea_level;
    water_=layer_or(world.water_type,n,0.);
    const Grid river=layer_or(world.river,n,0.);
    const Grid flood=layer_or(world.flood_risk,n,0.);
    const ValueLayer& biome=world.natural_biome;
    if(defined_) {
        for(std::size_t i=0;i<world.bands.size();++i)
            bands_.push_back(Band{world.bands[i].scale_m,world.bands[i].amplitude_m,
                                  static_cast<std::int64_t>(child_seed(
                                      static_cast<std::uint64_t>(world.detail_seed),
                                      std::to_string(i)))});
    }
    strength_.assign(n,std::vector<double>(n,0.));
    for(std::size_t z=0;z<n;++z)
        for(std::size_t x=0;x<n;++x)
            // A water cell short-circuits to 0., so the biome cell under it is never
            // looked up -- and an unhashable one there never raises, as in Python.
            strength_[z][x]=water_[z][x]!=0.?0.
                :std::max(0.,1-std::min(1.,river[z][x]*2))*std::max(0.,1-std::min(1.,flood[z][x]))
                 *(biome.present?biome_amplitude(biome.rows[z][x]):.8);
}
void HeightField::cell(const Vec3& p,std::size_t& ix,std::size_t& iz,std::size_t& jz,
                       double& fx,double& fz) const {
    const double span=static_cast<double>(n_-1);
    const double x=python_mod((std::atan2(p[2],p[0])+pi)/(2*pi)*span,span);
    double z=(pi/2-std::asin(std::max(-1.,std::min(1.,p[1]))))/pi*span;
    z=std::max(0.,std::min(span,z));
    ix=static_cast<std::size_t>(x);
    iz=static_cast<std::size_t>(z);
    jz=std::min(static_cast<std::size_t>(n_-1),iz+1);
    fx=x-static_cast<double>(ix);
    fz=z-static_cast<double>(iz);
}
double HeightField::height(const Vec3& p) const {
    if(!defined_) return fantasy_world_generator::sample(*base_,p);
    std::size_t ix=0,iz=0,jz=0;double fx=0.,fz=0.;
    cell(p,ix,iz,jz,fx,fz);
    const double base=at(*base_,ix,iz,jz,fx,fz);
    // Each factor can independently zero the detail, and the answer is `base` whenever
    // one does, so the remaining grid reads are skipped rather than multiplied by zero.
    const double coast=std::max(0.,std::min(1.,(base-sea_)/20.));
    if(coast==0.) return base;
    double strength=at(strength_,ix,iz,jz,fx,fz);
    strength=std::max(0.,(strength-.15)/.85);
    if(strength==0.) return base;
    const double wet=std::max(0.,1-2*at(water_,ix,iz,jz,fx,fz));
    strength*=coast*coast*(3-2*coast)*wet*wet;
    if(strength==0.) return base;
    // `sum(...)` over the bands: CPython's compensated float sum, not a plain +=.
    Sum detail;
    for(const Band& band:bands_)
        detail.add(band.amplitude*perlin3(p[0]*radius_/band.scale,p[1]*radius_/band.scale,
                                          p[2]*radius_/band.scale,band.seed));
    return base+strength*detail.value();
}

// ---------------------------------------------------------------------------
// world_scene.position
// ---------------------------------------------------------------------------
// `[(field.radius+height)*v for v in p]`. The reference re-evaluates `field.height(p)`
// once per component; it is a pure function of `p`, so it is evaluated once here.
Value position(const HeightField& field,const Vec3& p) {
    const double distance=field.radius()+field.height(p);
    Value out=varr();
    for(int i=0;i<3;++i) out.items.push_back(vflt(distance*p[i]));
    return out;
}
Value position_at(const HeightField& field,const Vec3& p,double height) {
    const double distance=field.radius()+height;
    Value out=varr();
    for(int i=0;i<3;++i) out.items.push_back(vflt(distance*p[i]));
    return out;
}

// ---------------------------------------------------------------------------
// The `gates` dict of build_scene, keyed by the tuple (route_index, end).
//
// A Python dict, so: insertion order is irrelevant to a lookup but a repeated key
// REPLACES the row rather than adding one, and `(2.0,'from')` and `(2,'from')` are the
// same key because `hash(2.0)==hash(2)`. A std::map<std::pair<int64,string>> would get
// the second of those wrong and would need the index to be an integer at all.
// ---------------------------------------------------------------------------
class Gates {
  public:
    void put(const Value& index,const Value& end,const Value* row) {
        for(Entry& entry:entries_)
            if(value_equal(entry.index,index)&&value_equal(entry.end,end)) {entry.row=row;return;}
        entries_.push_back(Entry{index,end,row});
    }
    const Value* get(std::int64_t index,const char* end) const {
        const Value key=vint(index);
        const Value tail=vstr(end);
        for(const Entry& entry:entries_)
            if(value_equal(entry.index,key)&&value_equal(entry.end,tail)) return entry.row;
        return nullptr;
    }
  private:
    struct Entry {Value index,end;const Value* row;};
    std::vector<Entry> entries_;
};

// ---------------------------------------------------------------------------
// world_scene._emit_local_plan
// ---------------------------------------------------------------------------
struct Lists {
    std::vector<Value> buildings,streets,junctions;
};

// `frame(world, site)` through the accepted sceneframe port. Only `x` and `z` of the site
// reach it, and only `size` and the radius of the world, so the adapter is this small.
sceneframe::Frame frame_of(const World& world,double x,double z) {
    sceneframe::World slice;
    slice.size=world.size;
    slice.config_globe_radius=world.globe_radius;
    sceneframe::Site site;
    site.x=x;
    site.z=z;
    return sceneframe::frame(slice,site);
}

void emit_local_plan(Lists& out,const World& world,const HeightField& field,
                     double site_x,double site_z,const Value& plan,
                     const char* settlement_kind,const char* uid_field,const Value& uid_value,
                     Gates* gates) {
    const sceneframe::Frame f=frame_of(world,site_x,site_z);
    const std::string label=py_str(uid_value);
    // `tag={'settlement_kind':settlement_kind, uid_field:uid_value}`, splatted second in
    // every record so it always follows `id`.
    const auto tag=[&](Value& record) {
        record.set("settlement_kind",vstr(settlement_kind));
        record.set(uid_field,uid_value);
    };
    const auto walk=[&](const Value& path) {
        Value positions=varr();
        for(const Value& point:path.items) {
            double x=0.,z=0.;
            local_point(point,x,z);
            positions.items.push_back(position(field,sceneframe::local_direction(f,x,z)));
        }
        return positions;
    };

    // `for i,path in enumerate(plan.get('street_paths_m',[]))`. A castle plan has no such
    // key at all -- its street runs live under 'roads' -- so the default is load bearing.
    const Value* paths=find_field(plan,"street_paths_m");
    if(paths!=nullptr) {
        if(!paths->is_array()) throw SceneError("'NoneType' object is not iterable");
        for(std::size_t i=0;i<paths->items.size();++i) {
            Value record=vobj();
            record.set("id",vstr(label+":street:"+std::to_string(i)));
            tag(record);
            record.set("positions_m",walk(paths->items[i]));
            out.streets.push_back(std::move(record));
        }
    }

    // `for c in plan.get('road_connections',[])`.
    const Value* connections=find_field(plan,"road_connections");
    if(connections!=nullptr) {
        if(!connections->is_array()) throw SceneError("'NoneType' object is not iterable");
        for(const Value& c:connections->items) {
            // Only a city passes `gates`; a hamlet or castle support entry carries
            // route_index -1 and would be rejected by the `>=0` test anyway.
            if(gates!=nullptr) {
                const Value* index=find_field(c,"route_index");
                const Value fallback=vint(-1);
                const Value& route_index=index!=nullptr?*index:fallback;
                if(at_least_zero(route_index)) gates->put(route_index,c.at("end"),&c);
            }
            const Value pos=position(field,as_vector(c.at("direction")));
            Value junction=vobj();
            junction.set("id",c.at("junction_id"));
            tag(junction);
            junction.set("route_id",c.at("route_id"));
            junction.set("position_m",pos);
            junction.set("status",c.at("status"));
            out.junctions.push_back(std::move(junction));
            if(value_equal(c.at("status"),vstr("connected"))) {
                Value vertices=walk(c.at("local_path_m"));
                // `vertices[-1]=pos` on an empty list raises, and an ASSIGNMENT to a
                // missing index has its own CPython sentence, not the reader's.
                if(vertices.items.empty())
                    throw SceneError("list assignment index out of range");
                vertices.items.back()=pos;
                const Value& junction_id=c.at("junction_id");
                if(junction_id.kind!=Value::Kind::String)
                    throw SceneError("can only concatenate str to str");
                Value record=vobj();
                record.set("id",vstr(junction_id.text+":approach"));
                tag(record);
                record.set("junction_id",junction_id);
                record.set("positions_m",std::move(vertices));
                out.streets.push_back(std::move(record));
            }
        }
    }

    // `for b in plan['plots']` -- not a .get: a plan with no plots key is a KeyError.
    const Value& plots=plan.at("plots");
    if(!plots.is_array()) throw SceneError("'NoneType' object is not iterable");
    for(const Value& b:plots.items) {
        const Vec3 p=sceneframe::local_direction(f,as_number(b.at("x_m")),as_number(b.at("z_m")));
        const double angle=py_radians(as_number(b.at("rotation_degrees")));
        // Reference line 68: `dot=sum(a*v for a,v in zip(f[2],p))`, a compensated sum of
        // three products. f[2] is the frame's east vector.
        Sum projection;
        for(int i=0;i<3;++i) projection.add(f.east[i]*p[i]);
        const double dot_up=projection.value();
        // Gram-Schmidt: the frame's east with the radial component removed, so the basis
        // is tangent at the PLOT rather than at the settlement centre.
        Vec3 east{};
        for(int i=0;i<3;++i) east[i]=f.east[i]-dot_up*p[i];
        // Reference line 69: `length=math.sqrt(sum(v*v for v in east))`, compensated too.
        Sum squares;
        for(int i=0;i<3;++i) squares.add(east[i]*east[i]);
        const double length=std::sqrt(squares.value());
        if(length==0.) throw SceneZeroDivision();
        for(int i=0;i<3;++i) east[i]=east[i]/length;
        // north = east x p, written out in the reference and not through a helper; the
        // component order is its own.
        const Vec3 north{east[1]*p[2]-east[2]*p[1],east[2]*p[0]-east[0]*p[2],
                         east[0]*p[1]-east[1]*p[0]};
        // The rotation. Plain products and one addition each, as in the reference: no
        // sum() here, so no compensation here either.
        Vec3 width_axis{},depth_axis{};
        for(int i=0;i<3;++i) {
            width_axis[i]=east[i]*std::cos(angle)+north[i]*std::sin(angle);
            depth_axis[i]=-east[i]*std::sin(angle)+north[i]*std::cos(angle);
        }
        // The plot's own ground elevation, not a fresh height sample: the planner already
        // rounded it to four digits and the footprint has to sit on that same plane.
        const Value center=position_at(field,p,as_number(b.at("ground_elevation_m")));
        const Value& dimensions=b.at("dimensions_m");
        const double width=as_number(dimensions.at("width"));
        const double depth=as_number(dimensions.at("depth"));
        const double offsets[4][2]={{-width/2,-depth/2},{width/2,-depth/2},
                                    {width/2,depth/2},{-width/2,depth/2}};
        Value footprint=varr();
        for(const auto& offset:offsets) {
            Value corner=varr();
            for(int k=0;k<3;++k)
                corner.items.push_back(vflt(as_number(center.items[k])
                                            +offset[0]*width_axis[k]+offset[1]*depth_axis[k]));
            footprint.items.push_back(std::move(corner));
        }
        Value record=vobj();
        record.set("id",vstr(label+":"+py_str(b.at("id"))));
        tag(record);
        record.set("plot_id",b.at("id"));
        record.set("asset_id",b.at("building_id"));
        record.set("position_m",center);
        record.set("up",from_vector(p));
        record.set("width_axis",from_vector(width_axis));
        record.set("depth_axis",from_vector(depth_axis));
        record.set("rotation_degrees",b.at("rotation_degrees"));
        record.set("dimensions_m",dimensions);
        record.set("footprint_positions_m",std::move(footprint));
        out.buildings.push_back(std::move(record));
    }
}

Value array_of(std::vector<Value> items) {
    Value out=varr();
    out.items=std::move(items);
    return out;
}

}  // namespace

Value build_scene(const World& world) {
    const HeightField field(world);
    const std::int64_t n=world.size;
    Lists lists;
    std::vector<Value> regional_roads;
    Gates gates;

    // ---- cities -----------------------------------------------------------
    for(const Value& city:world.city_plans) {
        const Value& uid=city.at("city_uid");
        // `next(s for s in sites if s.get('uid',str(s['id']))==city['city_uid'])`. The
        // fallback is stringified; a present uid is NOT, so an int uid and its decimal
        // spelling are different settlements here.
        const Value* site=nullptr;
        for(const Value& candidate:world.sites) {
            const Value* stored=find_field(candidate,"uid");
            const Value key=stored!=nullptr?*stored:vstr(py_str(candidate.at("id")));
            if(value_equal(key,uid)) {site=&candidate;break;}
        }
        // `next()` with no default: a bare StopIteration, which the reference lets out.
        if(site==nullptr) throw SceneStopIteration();
        emit_local_plan(lists,world,field,as_number(site->at("x")),as_number(site->at("z")),
                        city,"city","city_uid",uid,&gates);
    }
    // ---- hamlets ----------------------------------------------------------
    // The site is synthesized from the plan, not looked up, so a hamlet needs no
    // settlement row at all.
    for(const Value& plan:world.hamlet_plans)
        emit_local_plan(lists,world,field,as_number(plan.at("x")),as_number(plan.at("z")),
                        plan,"hamlet","hamlet_id",plan.at("hamlet_id"),nullptr);
    // ---- castles ----------------------------------------------------------
    for(const Value& plan:world.castle_plans)
        emit_local_plan(lists,world,field,as_number(plan.at("x")),as_number(plan.at("z")),
                        plan,"castle","fortress_id",plan.at("fortress_id"),nullptr);

    // ---- regional roads ---------------------------------------------------
    for(std::size_t index=0;index<world.routes.size();++index) {
        const Route& road=world.routes[index];
        const Value* a=gates.get(static_cast<std::int64_t>(index),"from");
        const Value* b=gates.get(static_cast<std::int64_t>(index),"to");
        const auto node_count=static_cast<std::int64_t>(road.nodes.size());
        const std::int64_t lo=a!=nullptr?as_index(a->at("outside_index")):0;
        const std::int64_t hi=b!=nullptr?as_index(b->at("outside_index"))+1:node_count;
        // `road['nodes'][lo:hi]`: Python slice clamping, which never raises and can be
        // empty when a city's gate sits past the other city's gate.
        const std::int64_t start=lo<0?std::max<std::int64_t>(0,lo+node_count)
                                     :std::min(lo,node_count);
        const std::int64_t stop=hi<0?std::max<std::int64_t>(0,hi+node_count)
                                    :std::min(hi,node_count);
        std::vector<Vec3> vectors;
        for(std::int64_t k=start;k<stop;++k) {
            const auto& point=node_at(world.water_nodes,road.nodes[static_cast<std::size_t>(k)]);
            vectors.push_back(direction(point.first,point.second,n));
        }
        // The gate directions replace nothing: they are inserted OUTSIDE the surviving
        // nodes, so the polyline starts and ends on the settlement boundary.
        if(a!=nullptr) vectors.insert(vectors.begin(),as_vector(a->at("direction")));
        if(b!=nullptr) vectors.push_back(as_vector(b->at("direction")));

        // Densify the polyline onto the same surface; route topology is unchanged.
        std::vector<Vec3> dense;
        for(std::size_t k=0;k+1<vectors.size();++k) {
            const Vec3& p=vectors[k];
            const Vec3& q=vectors[k+1];
            // Reference line 110: `sum(x*y for x,y in zip(p,q))`, compensated.
            Sum cosine;
            for(int j=0;j<3;++j) cosine.add(p[j]*q[j]);
            const double clamped=std::max(-1.,std::min(1.,cosine.value()));
            // `max(1, math.ceil(field.radius*math.acos(...)/4))`: ceil to a Python int,
            // then a floor of one so a degenerate pair still emits its own vertex.
            const double spacing=std::ceil(world.globe_radius*std::acos(clamped)/4);
            const std::int64_t count=std::max<std::int64_t>(1,static_cast<std::int64_t>(spacing));
            for(std::int64_t step=0;step<count;++step) {
                Vec3 v{};
                for(int j=0;j<3;++j)
                    v[j]=p[j]+(q[j]-p[j])*static_cast<double>(step)/static_cast<double>(count);
                // Reference line 112: `sum(x*x for x in v)`, compensated.
                Sum squares;
                for(int j=0;j<3;++j) squares.add(v[j]*v[j]);
                const double length=std::sqrt(squares.value());
                if(length==0.) throw SceneZeroDivision();
                dense.push_back(Vec3{v[0]/length,v[1]/length,v[2]/length});
            }
        }
        if(!vectors.empty()) dense.push_back(vectors.back());

        Value vertices=varr();
        for(const Vec3& p:dense) vertices.items.push_back(position(field,p));
        // The two endpoints are re-derived from the gate directions rather than from the
        // densified copy, so a junction and the road that meets it share a vertex exactly.
        if(a!=nullptr&&!vertices.items.empty())
            vertices.items.front()=position(field,as_vector(a->at("direction")));
        if(b!=nullptr&&!vertices.items.empty())
            vertices.items.back()=position(field,as_vector(b->at("direction")));

        Value record=vobj();
        record.set("id",vstr("regional-road-"+std::to_string(index)));
        record.set("source_route_index",vint(static_cast<std::int64_t>(index)));
        record.set("positions_m",std::move(vertices));
        record.set("from_junction",a!=nullptr?a->at("junction_id"):Value::make_null());
        record.set("to_junction",b!=nullptr?b->at("junction_id"):Value::make_null());
        record.set("from_status",a!=nullptr?a->at("status"):vstr("no_city_boundary"));
        record.set("to_status",b!=nullptr?b->at("status"):vstr("no_city_boundary"));
        record.set("bridge_candidates",road.river_crossings);
        regional_roads.push_back(std::move(record));
    }

    // The scene dict, in the reference's own key order. Every list below was appended to
    // in emission order and is handed over unsorted, because a Python dict and a Python
    // list both keep what they were given.
    Value scene=vobj();
    scene.set("version",vint(1));
    scene.set("unit",vstr("metres"));
    scene.set("coordinates",vstr("globe-centred XYZ; Y north; X at latitude 0 longitude 0; "
                                 "Z at latitude 0 longitude 90"));
    scene.set("radius_m",world.radius);
    scene.set("terrain_detail",world.terrain_detail);
    scene.set("buildings",array_of(std::move(lists.buildings)));
    scene.set("streets",array_of(std::move(lists.streets)));
    scene.set("junctions",array_of(std::move(lists.junctions)));
    scene.set("regional_roads",array_of(std::move(regional_roads)));
    scene.set("limits",vstr("Regional routes remain coarse transport proposals, including "
                            "unengineered bridge candidates; local connection failures are "
                            "explicit. Hamlet entries are tagged settlement_kind=hamlet and "
                            "castle entries settlement_kind=castle; both remain filterable "
                            "from city payloads."));
    return scene;
}
}
