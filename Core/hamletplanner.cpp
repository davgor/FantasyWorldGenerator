#include "hamletplanner.hpp"
#include "cityfortifications.hpp"
#include "numeric.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <map>
#include <set>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::hamletplanner {
namespace {
// math.degrees multiplies by this constant and math.radians by its reciprocal; neither
// divides, so the two are not exact inverses. The reference round-trips an angle through
// both on every candidate, and the drift that introduces is part of the answer.
constexpr double rad_to_deg=180.0/pi;
constexpr double deg_to_rad=pi/180.0;
double py_degrees(double radians) {return radians*rad_to_deg;}
double py_radians(double degrees) {return degrees*deg_to_rad;}
// round(x, n): the reference's decimal rounding, already ported for the fortifications.
double round_to(double value,int digits) {return fortification_round_digits(value,digits);}
// Python's // floors towards negative infinity.
std::int64_t floor_div(std::int64_t value,std::int64_t divisor) {
    std::int64_t quotient=value/divisor;
    if(value%divisor!=0 && ((value<0)!=(divisor<0))) --quotient;
    return quotient;
}
std::int64_t py_imod(std::int64_t value,std::int64_t divisor) {
    std::int64_t remainder=value%divisor;
    if(remainder!=0 && ((remainder<0)!=(divisor<0))) remainder+=divisor;
    return remainder;
}
// round(x) with no digits: C round() (half away from zero), then the halfway case redone
// half-to-even, which is exactly what float.__round__(None) does.
std::int64_t py_round(double value) {
    double rounded=std::round(value);
    if(std::fabs(value-rounded)==0.5) rounded=2.0*std::round(value/2.0);
    return static_cast<std::int64_t>(rounded);
}
// int(x) on a float truncates towards zero, where a floor would not.
std::int64_t py_trunc(double value) {return static_cast<std::int64_t>(std::trunc(value));}
// math.floor then an int: floor FIRST, because the cast alone truncates towards zero and
// would shift every negative coordinate by a cell.
std::int64_t py_floor(double value) {return static_cast<std::int64_t>(std::floor(value));}
// math.dist over two points: CPython's own vector norm, not the platform hypot.
double point_distance(double ax,double az,double bx,double bz) {
    return python_hypot(ax-bx,az-bz);
}
// `x ** 2` where x is a float and 2 a Python int: CPython converts the exponent and calls
// libm pow. On this platform that is the dynamic UCRT's pow, which is why the build links
// /MD; a static CRT differs by an ulp on a fraction of inputs.
double py_square(double value) {return std::pow(value,2.);}

Value vint(std::int64_t value) {return Value::make_int(value);}
Value vflt(double value) {return Value::make_float(value);}
Value vstr(std::string value) {return Value::make_string(std::move(value));}
Value vbool(bool value) {return Value::make_bool(value);}
Value varr() {return Value::make_array();}
Value vobj() {return Value::make_object();}
double as_number(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole_fits?static_cast<double>(value.whole):value.number;
    if(value.kind==Value::Kind::Float) return value.number;
    if(value.kind==Value::Kind::Bool) return value.boolean?1.:0.;
    throw PlannerError("Expected a numeric value");
}
// A registry count, bed total or staffing target. These are Python ints in every shipped
// catalogue and the reference sums them in exact integer arithmetic, so a float here
// would be summed a different way (compensated) and is refused rather than guessed at.
std::int64_t as_integer(const Value& value) {
    if(value.kind==Value::Kind::Int&&value.whole_fits) return value.whole;
    if(value.kind==Value::Kind::Bool) return value.boolean?1:0;
    throw PlannerError("Expected an integer registry value");
}
double field_number(const Value& owner,const std::string& key) {return as_number(owner.at(key));}
const Value* find_field(const Value& owner,const std::string& key) {
    return owner.is_object()?owner.find(key):nullptr;
}
const Value& field_or(const Value& owner,const std::string& key,const Value& fallback) {
    const Value* found=find_field(owner,key);
    return found!=nullptr?*found:fallback;
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
// Python truthiness, for `hamlet.get('access_nodes') or []` and `role or ''`.
bool truthy(const Value& value) {
    switch(value.kind) {
        case Value::Kind::Null: return false;
        case Value::Kind::Bool: return value.boolean;
        case Value::Kind::Int: return value.whole_fits?value.whole!=0:!value.text.empty();
        case Value::Kind::Float: return value.number!=0.;
        case Value::Kind::String: return !value.text.empty();
        case Value::Kind::Array: return !value.items.empty();
        case Value::Kind::Object: return !value.fields.empty();
    }
    return false;
}
// `int.from_bytes(sha256(text).digest()[:8],'big')`: the leading 64 bits of the digest,
// which is the full-width street seed the reference feeds to grow_roads and to the
// ellipse wobble.
std::uint64_t digest_prefix(const std::string& text) {
    const std::string hex=sha256(text);
    std::uint64_t value=0;
    for(std::size_t i=0;i<16&&i<hex.size();++i) {
        const char c=hex[i];
        const int nibble=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:c>='A'&&c<='F'?c-'A'+10:0;
        value=(value<<4)|static_cast<std::uint64_t>(nibble);
    }
    return value;
}
// `list[index]` with Python's semantics: a negative index counts from the end, anything
// past either end raises.
const Value& list_at(const std::vector<Value>& items,std::int64_t index) {
    const auto count=static_cast<std::int64_t>(items.size());
    const std::int64_t at=index<0?index+count:index;
    if(at<0||at>=count) throw PlannerError("list index out of range");
    return items[static_cast<std::size_t>(at)];
}

// ---------------------------------------------------------------------------
// terrain_detail.HeightField, over the raw rasters rather than a world envelope.
//
// DUPLICATED from cityplanner.cpp, where it lives in an anonymous namespace. Kept
// line-for-line with that copy; see the note in hamletplanner.hpp.
// ---------------------------------------------------------------------------
class HeightField {
  public:
    explicit HeightField(const World& world);
    bool defined() const {return defined_;}
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
Grid value_layer_or(const ValueLayer& layer,std::size_t n,double fallback) {
    if(!layer.present) return Grid(n,std::vector<double>(n,fallback));
    Grid out(layer.rows.size());
    for(std::size_t z=0;z<layer.rows.size();++z) {
        out[z].reserve(layer.rows[z].size());
        for(const Value& v:layer.rows[z]) out[z].push_back(as_number(v));
    }
    return out;
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
    const Grid biome=value_layer_or(world.natural_biome,n,3.);
    if(defined_) {
        for(std::size_t i=0;i<world.bands.size();++i)
            bands_.push_back(Band{world.bands[i].scale_m,world.bands[i].amplitude_m,
                                  static_cast<std::int64_t>(child_seed(
                                      static_cast<std::uint64_t>(world.detail_seed),
                                      std::to_string(i)))});
    }
    // The dict literal the reference indexes by biome code; an absent code is .65. A
    // float 5.0 hashes equal to the int 5, so the comparison is numeric.
    auto biome_factor=[](double code) {
        if(code==5.) return 1.4;
        if(code==3.) return .8;
        if(code==4.) return 1.;
        if(code==7.) return 1.;
        if(code==15.) return .8;
        return .65;
    };
    strength_.assign(n,std::vector<double>(n,0.));
    for(std::size_t z=0;z<n;++z)
        for(std::size_t x=0;x<n;++x)
            strength_[z][x]=water_[z][x]!=0.?0.
                :std::max(0.,1-std::min(1.,river[z][x]*2))*std::max(0.,1-std::min(1.,flood[z][x]))
                 *biome_factor(biome[z][x]);
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
// city_planner._sampler, which the reference imports by name.
//
// DUPLICATED from cityplanner.cpp for the same reason as HeightField above.
// ---------------------------------------------------------------------------
struct SampleResult {
    bool water=false;
    double slope=0.,flood=0.,height=0.,moisture=0.;
    std::int64_t gx=0,gz=0;
};
class Sampler {
  public:
    Sampler(const World& world,const Value& site,double half);
    SampleResult sample(double x,double z,bool with_slope=true) const;
    double resolution() const {return pi*radius_/static_cast<double>(n_-1);}
  private:
    double river_distance(double x,double z) const;
    Vec3 direction_at(double x,double z) const;
    const World* world_=nullptr;
    std::int64_t n_=0;
    double radius_=0.;
    Vec3 up_{},east_{},north_{};
    HeightField field_;
    // Each river centreline projected into the local tangent plane, already clipped.
    std::vector<std::array<double,4>> lines_;
};
Sampler::Sampler(const World& world,const Value& site,double half)
        : world_(&world),n_(world.size),radius_(world.globe_radius),field_(world) {
    if(n_-1==0) throw PlannerZeroDivision();
    const double span=static_cast<double>(n_-1);
    const double lat=pi/2-pi*field_number(site,"z")/span;
    const double lon=-pi+2*pi*field_number(site,"x")/span;
    up_=Vec3{std::cos(lat)*std::cos(lon),std::sin(lat),std::cos(lat)*std::sin(lon)};
    east_=Vec3{-std::sin(lon),0.,std::cos(lon)};
    north_=Vec3{-std::sin(lat)*std::cos(lon),std::cos(lat),-std::sin(lat)*std::sin(lon)};
    // `local(node)`: the gnomonic projection of a water-graph node, or None behind the
    // horizon guard at den<=.1.
    auto local=[&](const std::pair<std::int64_t,std::int64_t>& node,double& ox,double& oz) {
        const double la=pi/2-pi*static_cast<double>(node.second)/span;
        const double lo=-pi+2*pi*static_cast<double>(node.first)/span;
        const Vec3 p{std::cos(la)*std::cos(lo),std::sin(la),std::cos(la)*std::sin(lo)};
        const double den=dot(p,up_);
        if(den<=.1) return false;
        ox=radius_*dot(p,east_)/den;
        oz=radius_*dot(p,north_)/den;
        return true;
    };
    for(const auto& segment:world.river_segments) {
        const auto count=static_cast<std::int64_t>(world.water_nodes.size());
        if(segment.first<0||segment.first>=count||segment.second<0||segment.second>=count)
            throw PlannerError("list index out of range");
        double ax=0.,az=0.,bx=0.,bz=0.;
        if(!local(world.water_nodes[static_cast<std::size_t>(segment.first)],ax,az)) continue;
        if(!local(world.water_nodes[static_cast<std::size_t>(segment.second)],bx,bz)) continue;
        const double lo0=std::min(ax,bx),hi0=std::max(ax,bx);
        const double lo1=std::min(az,bz),hi1=std::max(az,bz);
        if(lo0<=half+40&&hi0>=-half-40&&lo1<=half+40&&hi1>=-half-40)
            lines_.push_back({ax,az,bx,bz});
    }
}
double Sampler::river_distance(double x,double z) const {
    double best=1e30;
    for(const auto& line:lines_) {
        const double dx=line[2]-line[0],dz=line[3]-line[1];
        const double square=dx*dx+dz*dz;
        // `(dx*dx+dz*dz or 1)`: an exactly zero length divides by one instead.
        const double denominator=square!=0.?square:1.;
        const double raw=((x-line[0])*dx+(z-line[1])*dz)/denominator;
        const double t=std::max(0.,std::min(1.,raw));
        best=std::min(best,python_hypot(x-line[0]-t*dx,z-line[1]-t*dz));
    }
    return best;
}
Vec3 Sampler::direction_at(double x,double z) const {
    Vec3 p{};
    for(int i=0;i<3;++i) p[i]=up_[i]+(east_[i]*x+north_[i]*z)/radius_;
    return unit(p);
}
SampleResult Sampler::sample(double x,double z,bool with_slope) const {
    const double span=static_cast<double>(n_-1);
    Vec3 p{};
    for(int i=0;i<3;++i) p[i]=up_[i]+(east_[i]*x+north_[i]*z)/radius_;
    p=unit(p);
    SampleResult out;
    // round() then % on Python ints: banker's rounding, then a floored modulo.
    out.gx=py_imod(py_round((std::atan2(p[2],p[0])+pi)/(2*pi)*span),n_-1);
    // The reference does NOT clamp before asin here, unlike HeightField._cell.
    out.gz=std::max<std::int64_t>(0,std::min<std::int64_t>(
        n_-1,py_round((pi/2-std::asin(p[1]))/pi*span)));
    const auto gx=static_cast<std::size_t>(out.gx);
    const auto gz=static_cast<std::size_t>(out.gz);
    const double distance=river_distance(x,z);
    out.slope=world_->slope.present?world_->slope.rows[gz][gx]:0.;
    if(field_.defined()&&with_slope) {
        const double dx=(field_.height(direction_at(x+1,z))-field_.height(direction_at(x-1,z)))/2;
        const double dz=(field_.height(direction_at(x,z+1))-field_.height(direction_at(x,z-1)))/2;
        out.slope=py_degrees(std::atan(python_hypot(dx,dz)));
    }
    const double river=world_->river.present?world_->river.rows[gz][gx]:0.;
    out.flood=(!lines_.empty()&&river>.5)?(distance<28?1.:0.)
              :(world_->flood_risk.present?world_->flood_risk.rows[gz][gx]:0.);
    const double water=world_->water_type.present?world_->water_type.rows[gz][gx]:0.;
    out.water=water!=0.||distance<12;
    out.height=field_.height(p);
    out.moisture=world_->moisture.present?world_->moisture.rows[gz][gx]:.5;
    return out;
}

// ---------------------------------------------------------------------------
// Role conditions
// ---------------------------------------------------------------------------
// `_coastal_role(role)`. `role or ''` turns None and '' into '', and the three membership
// tests that follow need a string; a truthy non-string would be a TypeError in the
// reference, so it is refused here rather than silently answering False.
bool coastal_role(const Value& role) {
    std::string text;
    if(truthy(role)) {
        if(!role.is_string()) throw PlannerError("argument of type 'role' is not iterable");
        text=role.text;
    }
    if(text=="harbor"||text=="fishing"||text=="landing"||text=="harbor + fishing") return true;
    if(text.find("harbor")!=std::string::npos) return true;
    if(text.find("fishing")!=std::string::npos) return true;
    return text=="landing";
}
struct RoleConditions {
    bool farming=false,resource=false,shore=false;
    // `conditions.get(name, False)`: the eighteen authored keys, and False for anything
    // the catalogue asks for that this table does not name.
    bool get(const std::string& name) const {
        if(name=="farming_support") return farming;
        if(name=="resource_support") return resource;
        if(name=="navigable_shore") return shore;
        if(name=="usable_groundwater") return false;
        if(name=="water_collection_or_delivery") return true;
        if(name=="flowing_water") return false;
        if(name=="reliable_wind") return false;
        if(name=="ore_and_fuel_supply") return resource;
        if(name=="food_surplus") return farming;
        if(name=="working_animals") return farming;
        if(name=="clay_and_fuel_supply") return false;
        if(name=="medicinal_supply") return false;
        if(name=="clear_sky_view") return true;
        if(name=="isolation_access") return true;
        if(name=="route_crossing") return false;
        if(name=="grade_change") return false;
        if(name=="retention_needed") return false;
        if(name=="defended_perimeter") return false;
        return false;
    }
};
RoleConditions role_conditions(const Value& hamlet) {
    // `hamlet.get('role','')`: an absent key is '', but a present None stays None, and
    // None is not 'farming' either way.
    const Value empty=Value::make_string("");
    const Value& role=field_or(hamlet,"role",empty);
    RoleConditions out;
    out.farming=role.is_string()&&role.text=="farming";
    out.resource=role.is_string()&&role.text=="resource";
    out.shore=coastal_role(role);
    return out;
}

// One candidate placement: a plot centre beside one anchor, on one side of the street.
struct Option {
    double x=0.,z=0.,degrees=0.,ax=0.,az=0.;
    std::vector<Cell> footprint;      // sorted
    std::vector<Cell> corridor;       // sorted
    double ground_min=0.,ground_max=0.;
};
bool intersects(const std::vector<Cell>& cells,const std::set<Cell>& other) {
    for(const Cell& c:cells) if(other.count(c)!=0) return true;
    return false;
}
bool subset(const std::vector<Cell>& cells,const std::set<Cell>& other) {
    for(const Cell& c:cells) if(other.count(c)==0) return false;
    return true;
}
std::vector<Cell> to_vector(const std::set<Cell>& cells) {return {cells.begin(),cells.end()};}
}   // namespace

Value planner_identity() {
    const settlementpresets::Identity registry=settlementpresets::registry_identity();
    Value identity=vobj();
    identity.set("schema_version",vint(registry.schema_version));
    identity.set("revision",vint(registry.revision));
    identity.set("sha256",vstr(registry.sha256));
    Value out=vobj();
    out.set("version",vint(planner_version));
    out.set("registry",std::move(identity));
    return out;
}

Value support_road_entries(const World& world,const Value& hamlet,double half) {
    Value entries=varr();
    const Value fallback=Value::make_array();
    const Value& raw=field_or(hamlet,"access_nodes",fallback);
    // `list(hamlet.get('access_nodes') or [])`.
    const std::vector<Value>& path=truthy(raw)?raw.items:fallback.items;
    if(path.size()<2||world.water_nodes.empty()) return entries;
    sceneframe::World scene;
    scene.size=world.size;
    scene.has_effective_config=true;
    scene.effective_globe_radius=world.globe_radius;
    scene.config_globe_radius=world.globe_radius;
    sceneframe::Site site;
    site.x=field_number(hamlet,"x");
    site.z=field_number(hamlet,"z");
    const sceneframe::Frame f=sceneframe::frame(scene,site);
    const double r=f.radius;
    const std::string label=py_str(hamlet.at("id"));
    const auto count=static_cast<std::int64_t>(world.water_nodes.size());
    // access_nodes runs from the hamlet toward the parent city.
    double prev[2]={0.,0.};
    for(std::size_t k=1;k<path.size();++k) {
        const std::int64_t index=as_integer(path[k]);
        if(index<0||index>=count) break;
        const auto& node=world.water_nodes[static_cast<std::size_t>(index)];
        // The nodes go through terrain_globe.direction, poles and seam wrap and all,
        // while the frame above does not. The two conventions meeting here is the
        // reference's behaviour, not an oversight of the port.
        const Vec3 p=direction(node.first,node.second,world.size);
        const double den=dot(p,f.up);
        // The horizon guard abandons the whole path, it does not skip the node.
        if(den<=0.) break;
        const double q[2]={r*dot(p,f.east)/den,r*dot(p,f.north)/den};
        if(std::max(std::fabs(q[0]),std::fabs(q[1]))>half) {
            bool have=false;
            double t=0.;
            for(int j=0;j<2;++j) {
                if(!(std::fabs(q[j])>half)) continue;
                const double denominator=q[j]-prev[j];
                if(denominator==0.) throw PlannerZeroDivision();
                const double candidate=((q[j]>0.?half:-half)-prev[j])/denominator;
                if(!have||candidate<t) {t=candidate;have=true;}
            }
            double gate[2]={0.,0.};
            // Both axes are interpolated even though only the exceeding one chose `t`.
            for(int j=0;j<2;++j) gate[j]=prev[j]+t*(q[j]-prev[j]);
            const Vec3 heading=sceneframe::local_direction(f,gate[0],gate[1]);
            Value entry=vobj();
            entry.set("route_id",vstr("support:"+label));
            entry.set("route_index",vint(-1));
            entry.set("end",vstr("to"));
            entry.set("outside_index",vint(0));
            entry.set("junction_id",vstr("junction:"+label+":support"));
            Value gate_value=varr();
            gate_value.items.push_back(vflt(gate[0]));
            gate_value.items.push_back(vflt(gate[1]));
            entry.set("gate_local_m",std::move(gate_value));
            Value direction_value=varr();
            for(int j=0;j<3;++j) direction_value.items.push_back(vflt(heading[j]));
            entry.set("direction",std::move(direction_value));
            entry.set("status",vstr("unreachable"));
            entry.set("reason",vstr("No terrain-safe street connection to parent-city approach"));
            entries.items.push_back(std::move(entry));
            break;
        }
        prev[0]=q[0];prev[1]=q[1];
    }
    return entries;
}

Value plan_hamlet(const World& world,const Value& hamlet) {
    const Value* profile=find_field(hamlet,"population_profile");
    if(profile==nullptr) throw PlannerError("'population_profile'");
    if(!profile->is_string()) throw PlannerError("Unknown civilization");
    const Value preset=settlementpresets::hamlet_plan(profile->text);
    const Value housing=settlementpresets::section("housing_profiles");
    const Value& house=housing.at("hamlet_house");
    const std::int64_t n=world.size;
    const double radius=world.globe_radius;
    const double hamlet_x=field_number(hamlet,"x"),hamlet_z=field_number(hamlet,"z");

    // Bound by the parent city and by neighbouring hamlets without moving anchors.
    double bound=static_cast<double>(half_default);
    {
        std::vector<const Value*> anchors;
        anchors.reserve(world.sites.size()+world.hamlets.size());
        for(const Value& site:world.sites) anchors.push_back(&site);
        const Value missing=Value::make_null();
        for(const Value& other:world.hamlets) {
            // `other is hamlet or other.get('id')==hamlet.get('id')`: identity first,
            // then the id, so two hamlets that both lack one are the same hamlet.
            if(&other==&hamlet) continue;
            if(value_equal(field_or(other,"id",missing),field_or(hamlet,"id",missing))) continue;
            anchors.push_back(&other);
        }
        for(const Value* other:anchors) {
            // `math.pi*hamlet['z']/(n-1)`: with a grid of size one CPython raises here,
            // before any coordinate exists.
            if(n-1==0) throw PlannerZeroDivision();
            const double span=static_cast<double>(n-1);
            const double lat1=pi/2-pi*hamlet_z/span;
            const double lat2=pi/2-pi*field_number(*other,"z")/span;
            const double dl=2*pi*(field_number(*other,"x")-hamlet_x)/span;
            const double cosine=std::sin(lat1)*std::sin(lat2)+std::cos(lat1)*std::cos(lat2)*std::cos(dl);
            const double distance=radius*std::acos(std::max(-1.,std::min(1.,cosine)));
            bound=std::min(bound,std::max(static_cast<double>(planner_cell),
                                          distance*.5-static_cast<double>(neighbour_gap)));
        }
    }
    // `int(half/CELL)*CELL` truncates towards zero; the window is a whole number of
    // cells from here on and every later use of `half` is that integer.
    const std::int64_t half=std::max<std::int64_t>(
        planner_cell,py_trunc(bound/static_cast<double>(planner_cell))*planner_cell);
    const std::int64_t size=floor_div(2*half,planner_cell);
    const double half_m=static_cast<double>(half);
    const double cell_m=static_cast<double>(planner_cell);
    if(n-1==0) throw PlannerZeroDivision();
    const double span=static_cast<double>(n-1);
    const Sampler sampler(world,hamlet,half_m);
    const double resolution=sampler.resolution();

    Value terrain_codes=varr(),terrain_biomes=varr(),terrain_variants=varr();
    std::set<Cell> valid;
    std::map<Cell,double> heights;
    for(std::int64_t j=0;j<size;++j) {
        Value row=varr(),biome_row=varr(),mutation_row=varr();
        for(std::int64_t i=0;i<size;++i) {
            const SampleResult v=sampler.sample(-half_m+(static_cast<double>(i)+.5)*cell_m,
                                                -half_m+(static_cast<double>(j)+.5)*cell_m);
            heights.emplace(Cell(i,j),v.height);
            // Coarse flood_risk is a regional layer, not a local inundation mask; unlike
            // the city planner's code, flood does not block a hamlet cell.
            const std::int64_t code=v.water?1:(v.slope>25?2:0);
            row.items.push_back(vint(code));
            const auto gx=static_cast<std::size_t>(v.gx);
            const auto gz=static_cast<std::size_t>(v.gz);
            biome_row.items.push_back(world.natural_biome.present
                ?world.natural_biome.rows[gz][gx]:vint(3));
            mutation_row.items.push_back(world.biome_variant.present
                ?world.biome_variant.rows[gz][gx]:vint(-1));
            // `slopes` and `woods` are accumulated by the reference and never read: the
            // hamlet record carries no `location` facts block. Nothing to port.
            if(code==0) valid.emplace(i,j);
        }
        terrain_codes.items.push_back(std::move(row));
        terrain_biomes.items.push_back(std::move(biome_row));
        terrain_variants.items.push_back(std::move(mutation_row));
    }
    const std::int64_t surface_size=size+1;
    Value surface=vobj();
    surface.set("size",vint(surface_size));
    surface.set("step_m",vflt(2*half_m/static_cast<double>(surface_size-1)));
    Value heights_m=varr();
    for(std::int64_t j=0;j<surface_size;++j) {
        Value row=varr();
        // `i*2*half/(surface_size-1)`: an exact integer product, then a float division.
        const double sz=-half_m+static_cast<double>(j*2*half)/static_cast<double>(surface_size-1);
        for(std::int64_t i=0;i<surface_size;++i) {
            const double sx=-half_m+static_cast<double>(i*2*half)/static_cast<double>(surface_size-1);
            row.items.push_back(vflt(round_to(sampler.sample(sx,sz,false).height,4)));
        }
        heights_m.items.push_back(std::move(row));
    }
    surface.set("heights_m",std::move(heights_m));
    surface.set("source",vstr("canonical terrain height in metres"));
    // `world.get('terrain_detail')`: the raw value, whatever HeightField made of it. A
    // default-constructed Value is Null, which is what an absent key serializes as.
    surface.set("terrain_detail",world.terrain_detail);
    surface.set("coordinates",vstr("local east/north gnomonic coordinates; radial elevation "
                                   "above reference sphere"));

    const Value& core=list_at(world.sites,as_integer(hamlet.at("core_id")));
    Value terrain=vobj();
    terrain.set("cell_m",vint(planner_cell));
    terrain.set("size",vint(size));
    terrain.set("codes",std::move(terrain_codes));
    terrain.set("surface",std::move(surface));
    terrain.set("natural_biome",std::move(terrain_biomes));
    terrain.set("biome_variant",std::move(terrain_variants));
    terrain.set("biome_catalogue",world.biome_catalogue.kind==Value::Kind::Null
                ?varr():world.biome_catalogue);
    terrain.set("magical_catalogue",world.magical_catalogue.kind==Value::Kind::Null
                ?varr():world.magical_catalogue);
    Value colors=vobj();
    for(const auto& entry:world.magic_colors) colors.set(entry.first,entry.second);
    terrain.set("magic_colors",std::move(colors));

    Value reference_frame=vobj();
    reference_frame.set("radius_m",world.radius);
    reference_frame.set("latitude_degrees",vflt(90-180*hamlet_z/span));
    reference_frame.set("longitude_degrees",vflt(-180+360*hamlet_x/span));
    reference_frame.set("projection",vstr("direction=normalize(up+(east*x_m+north*z_m)/radius_m); "
                                          "position=(radius_m+height_m)*direction"));

    Value shape=vobj();
    shape.set("shape_id",vstr("hamlet_compact"));
    shape.set("family",vstr("organic"));
    Value parameters=vobj();
    parameters.set("block_spacing_m",vint(48));
    parameters.set("aspect_ratio",vflt(1.1));
    shape.set("parameters",std::move(parameters));

    Value passes=varr();
    for(const char* key:{"map","shape","high","high_housing","low","low_housing"}) {
        Value pass=vobj();
        pass.set("id",vstr(key));
        pass.set("placed",vint(0));
        passes.items.push_back(std::move(pass));
    }
    Value warnings=varr();
    warnings.items.push_back(vstr("Schematic rural packing; groundwater and structural "
                                  "feasibility are not resolved."));
    warnings.items.push_back(vstr("Hamlet cottages use dedicated rural housing IDs, not city "
                                  "worker houses."));
    warnings.items.push_back(vstr("Compact elliptical boundary is provisional; historical "
                                  "village morphology is future work."));
    warnings.items.push_back(vstr("Regional flood_risk does not empty hamlet plots; standing "
                                  "water and slopes above 25 degrees still block cells."));

    Value bounds=varr();
    bounds.items.push_back(vint(-half));bounds.items.push_back(vint(-half));
    bounds.items.push_back(vint(half));bounds.items.push_back(vint(half));

    const Value null_value=Value::make_null();
    Value result=vobj();
    result.set("version",vint(planner_version));
    result.set("hamlet_id",hamlet.at("id"));
    result.set("kind",vstr("hamlet"));
    result.set("role",field_or(hamlet,"role",null_value));
    // `core.get('uid', str(core['id']))`: the default is evaluated eagerly, so a core
    // site with no 'id' raises even when it does carry a 'uid'.
    const Value core_id_text=vstr(py_str(core.at("id")));
    const Value* core_uid=find_field(core,"uid");
    result.set("core_city_uid",core_uid!=nullptr?*core_uid:core_id_text);
    result.set("core_id",hamlet.at("core_id"));
    result.set("x",hamlet.at("x"));
    result.set("z",hamlet.at("z"));
    result.set("node",hamlet.at("node"));
    result.set("civilization_id",*profile);
    result.set("unit",vstr("metres"));
    result.set("bounds_m",std::move(bounds));
    result.set("terrain",std::move(terrain));
    result.set("reference_frame",std::move(reference_frame));
    result.set("shape",std::move(shape));
    result.set("plots",varr());
    result.set("roads",varr());
    result.set("unplaced",varr());
    result.set("passes",std::move(passes));
    result.set("warnings",std::move(warnings));
    result.set("source_resolution_m",vflt(round_to(resolution,2)));
    result.set("status",vstr("unbuildable"));
    result.set("stats",vobj());
    Value debug=vobj();
    debug.set("terrain_safe_cells",vint(static_cast<std::int64_t>(valid.size())));
    debug.set("total_cells",vint(size*size));
    debug.set("housing_passes",varr());
    debug.set("apartment_policy",vstr("hamlet_houses_only"));
    result.set("debug",std::move(debug));
    result.set("road_connections",support_road_entries(world,hamlet,half_m));
    if(resolution>half_m)
        result.find("warnings")->items.push_back(
            vstr("Regional land categories repeat coarse samples; canonical local relief "
                 "supplies finer elevation detail."));

    // The two early returns share a body: nothing was placed, so every requirement is
    // unplaced and the stats block has five keys rather than nine.
    const Value* preset_buildings=find_field(preset,"buildings");
    auto give_up=[&]() {
        Value unplaced=varr();
        if(preset_buildings!=nullptr)
            for(const Value& row:preset_buildings->items) {
                Value entry=vobj();
                entry.set("building_id",row.at("structure_id"));
                entry.set("count",row.at("count"));
                entry.set("reason",vstr("No compatible buildable footprint"));
                unplaced.items.push_back(std::move(entry));
            }
        result.set("unplaced",std::move(unplaced));
        Value stats=vobj();
        stats.set("workers",vint(0));
        stats.set("worker_beds",vint(0));
        stats.set("housing_shortfall",vint(0));
        stats.set("service_buildings",vint(0));
        stats.set("houses",vint(0));
        result.set("stats",std::move(stats));
    };
    if(valid.size()<8) {give_up();return result;}

    result.find("passes")->items[0].set("placed",vint(static_cast<std::int64_t>(valid.size())));
    result.find("passes")->items[1].set("placed",vint(1));
    const std::int64_t spacing=48;
    const double rx=half_m*.9,rz=half_m*.9/1.1;
    // The street seed is the full leading 64 bits of the digest, not a truncated int.
    const std::uint64_t seed=digest_prefix(std::to_string(world.seed)+":"
                                           +py_str(result.at("hamlet_id"))+":hamlet-streets-v1");
    // Seeded irregular ellipse keeps city shape catalogues independent. The seed reaches
    // math.sin/cos as a float: a Python int added to a float is converted, rounded to
    // nearest, exactly as this cast is.
    const double seed_f=static_cast<double>(seed);
    const double wobble=0.08+0.04*(static_cast<double>(seed%1000)/1000);
    auto inside=[&](double x,double z) {
        return py_square(x/(rx*(1+wobble*std::sin(x*.07+seed_f))))
              +py_square(z/(rz*(1+wobble*std::cos(z*.09+seed_f))))<1;
    };
    {
        std::set<Cell> clipped;
        for(const Cell& c:valid)
            if(inside(-half_m+(static_cast<double>(c.first)+.5)*cell_m,
                      -half_m+(static_cast<double>(c.second)+.5)*cell_m))
                clipped.insert(c);
        valid.swap(clipped);
    }
    if(valid.size()<8) {give_up();return result;}

    // The gate cells, and the street network grown towards them.
    std::vector<Cell> entry_cells;
    {
        Value* entries=result.find("road_connections");
        for(Value& entry:entries->items) {
            Value cell=varr();
            std::int64_t coordinates[2]={0,0};
            const Value& gate=entry.at("gate_local_m");
            for(int j=0;j<2;++j) {
                const double v=as_number(gate.items[static_cast<std::size_t>(j)]);
                coordinates[j]=std::max<std::int64_t>(
                    0,std::min<std::int64_t>(size-1,py_floor((v+half_m)/cell_m)));
                cell.items.push_back(vint(coordinates[j]));
            }
            entry.set("cell",std::move(cell));
            entry_cells.emplace_back(coordinates[0],coordinates[1]);
        }
    }
    std::vector<Cell> gates;
    for(const Cell& cell:entry_cells) if(valid.count(cell)!=0) gates.push_back(cell);
    // Rural streets stay inside the ellipse with a low branch floor; the city's
    // 12-district growth would fill a 100 m window.
    const RoadNetwork network=grow_roads(valid,heights,size,seed,
                                         static_cast<double>(spacing)/static_cast<double>(planner_cell),
                                         gates,2);
    const std::set<Cell>& road=network.roads;
    {
        Value* entries=result.find("road_connections");
        for(std::size_t e=0;e<entries->items.size();++e) {
            Value& entry=entries->items[e];
            const Cell cell=entry_cells[e];
            const Value& gate=entry.at("gate_local_m");
            const double gx=as_number(gate.items[0]),gz=as_number(gate.items[1]);
            const double px=-half_m+(static_cast<double>(cell.first)+.5)*cell_m;
            const double pz=-half_m+(static_cast<double>(cell.second)+.5)*cell_m;
            const SampleResult v=sampler.sample(gx,gz);
            const double length=point_distance(px,pz,gx,gz);
            if(road.count(cell)==0||v.water||!(v.flood<=.65)||!(v.slope<=25)
               ||!(std::fabs(v.height-heights.at(cell))<=.35*length+1e-6)) continue;
            const std::vector<Cell>* approach=nullptr;
            for(const std::vector<Cell>& path:network.paths)
                if(!path.empty()&&path.back()==cell) {approach=&path;break;}
            Value local_path=varr();
            if(approach!=nullptr)
                for(const Cell& step:*approach) {
                    Value point=varr();
                    point.items.push_back(vflt(-half_m+(static_cast<double>(step.first)+.5)*cell_m));
                    point.items.push_back(vflt(-half_m+(static_cast<double>(step.second)+.5)*cell_m));
                    local_path.items.push_back(std::move(point));
                }
            else {
                Value point=varr();
                point.items.push_back(vflt(-half_m+(static_cast<double>(cell.first)+.5)*cell_m));
                point.items.push_back(vflt(-half_m+(static_cast<double>(cell.second)+.5)*cell_m));
                local_path.items.push_back(std::move(point));
            }
            local_path.items.push_back(gate);
            // `c.update(...)`: status and reason keep their places, local_path_m is new
            // and lands after `cell`.
            entry.set("status",vstr("connected"));
            entry.set("reason",vstr("Terrain-safe junction to parent-city approach"));
            entry.set("local_path_m",std::move(local_path));
        }
    }
    {
        Value roads=varr();
        for(const Cell& c:road) {
            Value pair=varr();
            pair.items.push_back(vint(c.first));
            pair.items.push_back(vint(c.second));
            roads.items.push_back(std::move(pair));
        }
        result.set("roads",std::move(roads));
    }
    Value street_paths=varr();
    for(const std::vector<Cell>& path:network.paths) {
        Value line=varr();
        for(const Cell& step:path) {
            Value point=varr();
            point.items.push_back(vflt(round_to(-half_m+(static_cast<double>(step.first)+.5)*cell_m,2)));
            point.items.push_back(vflt(round_to(-half_m+(static_cast<double>(step.second)+.5)*cell_m,2)));
            line.items.push_back(std::move(point));
        }
        street_paths.items.push_back(std::move(line));
    }
    result.set("street_paths_m",std::move(street_paths));

    // Anchors: a point every cell along every street, facing the local heading with a
    // seeded wobble. `sorted(set(...))` -- the key carries the whole tuple, so the order
    // is total and the set's own iteration order cannot reach the answer.
    struct Anchor {double x,z,angle;};
    std::vector<Anchor> anchors;
    {
        struct Less {
            bool operator()(const std::array<double,3>& a,const std::array<double,3>& b) const {
                for(int i=0;i<3;++i) {if(a[i]<b[i]) return true;if(b[i]<a[i]) return false;}
                return false;
            }
        };
        std::set<std::array<double,3>,Less> seen;
        const Value& paths=result.at("street_paths_m");
        for(const Value& path:paths.items) {
            const auto length=static_cast<std::int64_t>(path.items.size());
            for(std::int64_t i=0;i<length;++i) {
                const Value& a=path.items[static_cast<std::size_t>(std::max<std::int64_t>(0,i-3))];
                const Value& b=path.items[static_cast<std::size_t>(std::min<std::int64_t>(length-1,i+3))];
                const double ax=as_number(a.items[0]),az=as_number(a.items[1]);
                const double bx=as_number(b.items[0]),bz=as_number(b.items[1]);
                if(ax==bx&&az==bz) continue;                      // `if a==b: continue`
                const double x=as_number(path.items[static_cast<std::size_t>(i)].items[0]);
                const double z=as_number(path.items[static_cast<std::size_t>(i)].items[1]);
                double angle=std::atan2(bz-az,bx-ax);
                angle+=py_radians(5*std::sin(x*.13+z*.17+static_cast<double>(seed%1000)));
                if(seen.insert(std::array<double,3>{x,z,angle}).second)
                    anchors.push_back(Anchor{x,z,angle});
            }
        }
        std::stable_sort(anchors.begin(),anchors.end(),[](const Anchor& a,const Anchor& b) {
            const double ka=py_square(a.x)+py_square(a.z),kb=py_square(b.x)+py_square(b.z);
            if(ka!=kb) return ka<kb;
            if(a.x!=b.x) return a.x<b.x;
            if(a.z!=b.z) return a.z<b.z;
            return a.angle<b.angle;
        });
    }

    std::set<Cell> occupied,access;
    std::map<std::pair<double,double>,std::vector<Option>> candidate_cache;
    const double grade_factor=std::tan(py_radians(25));
    auto cells_at=[&](double x,double z,double w,double d,double angle) {
        return footprint_cells(x,z,w,d,angle,half_m,cell_m);
    };
    auto candidates=[&](double w,double d)->const std::vector<Option>& {
        const std::pair<double,double> key(w,d);
        const auto found=candidate_cache.find(key);
        if(found!=candidate_cache.end()) return found->second;
        std::vector<Option> options;
        for(const Anchor& anchor:anchors) {
            const double ax=anchor.x,az=anchor.z;
            // `angle` is the loop variable, and the body rebinds it. The rebinding
            // survives into the SECOND side, so side -1 is laid out from the rounded
            // heading rather than from the anchor's own. That is the reference's
            // behaviour (hamlet_planner.py:180-184) and it is reproduced here.
            double angle=anchor.angle;
            for(int s=0;s<2;++s) {
                const double side=s==0?1.:-1.;
                const double dx=-std::sin(angle)*side,dz=std::cos(angle)*side;
                const double x=round_to(ax+dx*(d/2+8),2),z=round_to(az+dz*(d/2+8),2);
                const double degrees=round_to(py_degrees(angle),4);
                angle=py_radians(degrees);
                const std::set<Cell> footprint_set=cells_at(x,z,w,d,angle);
                const std::vector<Cell> footprint=to_vector(footprint_set);
                if(!subset(footprint,valid)||intersects(footprint,road)) continue;
                double ground_min=0.,ground_max=0.;
                bool first=true;
                auto observe=[&](double value) {
                    if(first) {ground_min=ground_max=value;first=false;return;}
                    ground_min=std::min(ground_min,value);ground_max=std::max(ground_max,value);
                };
                for(const auto& corner:corners(x,z,w,d,angle))
                    observe(sampler.sample(corner.first,corner.second,false).height);
                for(const Cell& c:footprint) observe(heights.at(c));
                if(ground_max-ground_min>python_hypot(w,d)*grade_factor) continue;
                const double ex=x-dx*d/2,ez=z-dz*d/2;
                std::set<Cell> corridor;
                for(int t=0;t<11;++t) {
                    const std::set<Cell> step=cells_at(ax+(ex-ax)*t/10,az+(ez-az)*t/10,4,4,0);
                    corridor.insert(step.begin(),step.end());
                }
                const std::vector<Cell> corridor_cells=to_vector(corridor);
                if(!subset(corridor_cells,valid)) continue;
                Option option;
                option.x=x;option.z=z;option.degrees=degrees;option.ax=ax;option.az=az;
                option.footprint=footprint;option.corridor=corridor_cells;
                option.ground_min=ground_min;option.ground_max=ground_max;
                options.push_back(std::move(option));
            }
        }
        return candidate_cache.emplace(key,std::move(options)).first->second;
    };
    // `sum(r['target'] for r in row.get('staffing',{}).get('roles',[]))`, in exact
    // integer arithmetic because every authored target is a Python int.
    auto staffing_workers=[](const Value& row)->std::int64_t {
        const Value* staffing=find_field(row,"staffing");
        if(staffing==nullptr) return 0;
        const Value* roles=find_field(*staffing,"roles");
        if(roles==nullptr) return 0;
        std::int64_t total=0;
        for(const Value& entry:roles->items) total+=as_integer(entry.at("target"));
        return total;
    };
    auto install=[&](const Value& row,const std::string& phase,const char* kind)->bool {
        const Value& plot_m=row.at("plot_m");
        const double w=field_number(plot_m,"width"),d=field_number(plot_m,"depth");
        for(const Option& option:candidates(w,d)) {
            if(intersects(option.footprint,occupied)||intersects(option.footprint,access)
               ||intersects(option.corridor,occupied)) continue;
            occupied.insert(option.footprint.begin(),option.footprint.end());
            for(const Cell& c:option.corridor)
                if(!std::binary_search(option.footprint.begin(),option.footprint.end(),c))
                    access.insert(c);
            Value* plots=result.find("plots");
            Value plot=vobj();
            plot.set("id",vstr("plot-"+std::to_string(plots->items.size())));
            const Value* structure=find_field(row,"structure_id");
            plot.set("building_id",structure!=nullptr?*structure:field_or(row,"id",null_value));
            plot.set("name",row.at("name"));
            plot.set("kind",vstr(kind));
            plot.set("phase",vstr(phase));
            plot.set("x_m",vflt(option.x));
            plot.set("z_m",vflt(option.z));
            plot.set("rotation_degrees",vflt(option.degrees));
            plot.set("ground_elevation_m",vflt(round_to(option.ground_max,4)));
            plot.set("foundation_bottom_m",vflt(round_to(option.ground_min,4)));
            plot.set("plot_m",plot_m);
            plot.set("dimensions_m",row.at("dimensions_m"));
            Value road_access=varr();
            road_access.items.push_back(vflt(option.ax));
            road_access.items.push_back(vflt(option.az));
            plot.set("road_access",std::move(road_access));
            plot.set("workers",vint(staffing_workers(row)));
            const Value* beds=find_field(row,"worker_beds");
            plot.set("beds",beds!=nullptr?*beds:vint(0));
            plots->items.push_back(std::move(plot));
            Value* passes_value=result.find("passes");
            for(Value& pass:passes_value->items)
                if(pass.at("id").text==phase) {
                    pass.set("placed",vint(as_integer(pass.at("placed"))+1));
                    break;
                }
            return true;
        }
        return false;
    };
    auto plot_total=[&](const char* key)->std::int64_t {
        std::int64_t total=0;
        for(const Value& plot:result.at("plots").items) total+=as_integer(plot.at(key));
        return total;
    };

    const RoleConditions conditions=role_conditions(hamlet);
    std::vector<const Value*> high,low;
    if(preset_buildings!=nullptr)
        for(const Value& row:preset_buildings->items) {
            std::string missing;
            bool any=false;
            for(const Value& condition:row.at("placement_conditions").items)
                if(!conditions.get(condition.text)) {
                    if(any) missing+=", ";
                    missing+=condition.text;
                    any=true;
                }
            if(any) {
                Value entry=vobj();
                entry.set("building_id",row.at("structure_id"));
                entry.set("count",row.at("count"));
                entry.set("reason",vstr("Unverified prerequisite: "+missing));
                result.find("unplaced")->items.push_back(std::move(entry));
                continue;
            }
            (row.at("priority").text=="core"?high:low).push_back(&row);
        }
    auto house_workers=[&](const std::string& phase) {
        std::int64_t workers=plot_total("workers"),beds=plot_total("beds");
        const std::int64_t starting=beds;
        std::int64_t placed=0;
        bool exhausted=false;
        const std::int64_t house_beds=as_integer(house.at("worker_beds"));
        while(beds<workers) {
            if(!install(house,phase,"housing")) {exhausted=true;break;}
            ++placed;
            beds+=house_beds;
        }
        Value audit=vobj();
        audit.set("phase",vstr(phase));
        audit.set("workers",vint(workers));
        audit.set("starting_beds",vint(starting));
        audit.set("houses_placed",vint(placed));
        audit.set("upgrades",vint(0));
        audit.set("plots_exhausted",vbool(exhausted));
        audit.set("final_beds",vint(beds));
        audit.set("shortfall",vint(std::max<std::int64_t>(0,workers-beds)));
        result.find("debug")->find("housing_passes")->items.push_back(std::move(audit));
    };
    for(int pass=0;pass<2;++pass) {
        const std::string priority=pass==0?"high":"low";
        const std::vector<const Value*>& rows=pass==0?high:low;
        if(pass==1) {
            std::int64_t shortfall=0;
            for(const Value& plot:result.at("plots").items)
                shortfall+=as_integer(plot.at("workers"))-as_integer(plot.at("beds"));
            if(shortfall>0) {
                for(const Value* row:rows) {
                    Value entry=vobj();
                    entry.set("building_id",row->at("structure_id"));
                    entry.set("count",row->at("count"));
                    entry.set("reason",vstr("High-priority worker housing must be completed first"));
                    result.find("unplaced")->items.push_back(std::move(entry));
                }
                break;
            }
        }
        for(const Value* row:rows) {
            std::int64_t failed=0;
            const std::int64_t count=as_integer(row->at("count"));
            for(std::int64_t k=0;k<count;++k) if(!install(*row,priority,"service")) ++failed;
            if(failed!=0) {
                Value entry=vobj();
                entry.set("building_id",row->at("structure_id"));
                entry.set("count",vint(failed));
                entry.set("reason",vstr("No terrain-safe plot with road access remaining"));
                result.find("unplaced")->items.push_back(std::move(entry));
            }
        }
        house_workers(priority+"_housing");
    }

    const std::int64_t workers=plot_total("workers"),beds=plot_total("beds");
    {
        const Value& house_plot=house.at("plot_m");
        const std::size_t frontage=candidates(field_number(house_plot,"width"),
                                              field_number(house_plot,"depth")).size();
        Value* debug_value=result.find("debug");
        debug_value->set("shape_safe_cells",vint(static_cast<std::int64_t>(valid.size())));
        debug_value->set("road_cells",vint(static_cast<std::int64_t>(road.size())));
        debug_value->set("occupied_cells",vint(static_cast<std::int64_t>(occupied.size())));
        debug_value->set("access_cells",vint(static_cast<std::int64_t>(access.size())));
        std::int64_t vacant=0;
        for(const Cell& c:valid)
            if(road.count(c)==0&&occupied.count(c)==0&&access.count(c)==0) ++vacant;
        debug_value->set("vacant_shape_cells",vint(vacant));
        debug_value->set("housing_frontage_candidates",vint(static_cast<std::int64_t>(frontage)));
    }
    std::set<std::string> core_ids;
    if(preset_buildings!=nullptr)
        for(const Value& row:preset_buildings->items)
            if(row.at("priority").text=="core") core_ids.insert(row.at("structure_id").text);
    std::int64_t failed_core=0,unplaced_total=0;
    for(const Value& row:result.at("unplaced").items) {
        const std::int64_t count=as_integer(row.at("count"));
        unplaced_total+=count;
        const Value& id=row.at("building_id");
        if(id.is_string()&&core_ids.count(id.text)!=0) failed_core+=count;
    }
    result.set("status",vstr(failed_core==0&&beds>=workers?"complete":"partial"));
    std::int64_t service=0,houses=0,area=0;
    const Value& house_id=house.at("id");
    for(const Value& plot:result.at("plots").items) {
        if(plot.at("kind").text=="service") ++service;
        if(value_equal(plot.at("building_id"),house_id)) ++houses;
        const Value& plot_m=plot.at("plot_m");
        area+=as_integer(plot_m.at("width"))*as_integer(plot_m.at("depth"));
    }
    Value stats=vobj();
    stats.set("workers",vint(workers));
    stats.set("worker_beds",vint(beds));
    stats.set("housing_shortfall",vint(std::max<std::int64_t>(0,workers-beds)));
    stats.set("service_buildings",vint(service));
    stats.set("houses",vint(houses));
    stats.set("apartments",vint(0));
    stats.set("unplaced_core",vint(failed_core));
    stats.set("unplaced_total",vint(unplaced_total));
    stats.set("reserved_plot_area_m2",vint(area));
    result.set("stats",std::move(stats));
    return result;
}

Value fill_hamlets(const World& world) {
    // `sorted(..., key=lambda h: str(h['id']))`: a stable sort on the decimal spelling of
    // the id, so an integer id sorts as text and ties keep list order.
    std::vector<std::size_t> order(world.hamlets.size());
    for(std::size_t i=0;i<order.size();++i) order[i]=i;
    std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
        return py_str(world.hamlets[a].at("id"))<py_str(world.hamlets[b].at("id"));
    });
    Value hamlets=varr();
    for(std::size_t index:order) hamlets.items.push_back(plan_hamlet(world,world.hamlets[index]));
    Value phase_order=varr();
    for(const char* key:{"map","shape","high","high_housing","low","low_housing"})
        phase_order.items.push_back(vstr(key));
    Value out=vobj();
    out.set("version",vint(planner_version));
    out.set("identity",planner_identity());
    out.set("hamlets",std::move(hamlets));
    out.set("phase_order",std::move(phase_order));
    out.set("scope",vstr("Schematic local metres for support hamlets; independent of "
                         "city_plans; does not change simulated population."));
    return out;
}
}
