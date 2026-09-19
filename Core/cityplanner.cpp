#include "cityplanner.hpp"
#include "cityshapes.hpp"
#include "numeric.hpp"
#include "pyrandom.hpp"
#include <algorithm>
#include <array>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::cityplanner {
namespace {
// math.degrees multiplies by this constant and math.radians by its reciprocal; neither
// divides, so the two are not exact inverses and the reference depends on that.
constexpr double rad_to_deg=180.0/pi;
constexpr double deg_to_rad=pi/180.0;
double py_degrees(double radians) {return radians*rad_to_deg;}
double py_radians(double degrees) {return degrees*deg_to_rad;}
// round(x) with no digits: C round() (half away from zero), then the halfway case
// redone half-to-even, which is exactly what float.__round__(None) does.
std::int64_t py_round(double value) {
    double rounded=std::round(value);
    if(std::fabs(value-rounded)==0.5) rounded=2.0*std::round(value/2.0);
    return static_cast<std::int64_t>(rounded);
}
double round_to(double value,int digits) {return fortification_round_digits(value,digits);}
// Python's // floors towards negative infinity and % follows the divisor's sign.
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
// math.dist over two points: CPython's own vector norm, not the platform hypot.
double point_distance(double ax,double az,double bx,double bz) {
    return python_hypot(ax-bx,az-bz);
}

Value vint(std::int64_t value) {return Value::make_int(value);}
Value vflt(double value) {return Value::make_float(value);}
Value vstr(std::string value) {return Value::make_string(std::move(value));}
Value vbool(bool value) {return Value::make_bool(value);}
Value varr() {return Value::make_array();}
Value vobj() {return Value::make_object();}
Value vpair(double a,double b) {
    Value out=varr();out.items.push_back(vflt(a));out.items.push_back(vflt(b));return out;
}
double as_number(const Value& value) {
    if(value.kind==Value::Kind::Int) return value.whole_fits?static_cast<double>(value.whole):value.number;
    if(value.kind==Value::Kind::Float) return value.number;
    if(value.kind==Value::Kind::Bool) return value.boolean?1.:0.;
    throw PlannerError("Expected a numeric registry value");
}
double field_number(const Value& owner,const std::string& key) {return as_number(owner.at(key));}
std::int64_t field_int(const Value& owner,const std::string& key) {
    const Value& child=owner.at(key);
    if(child.kind==Value::Kind::Int) return child.whole;
    return static_cast<std::int64_t>(as_number(child));
}
const Value* find_field(const Value& owner,const std::string& key) {
    return owner.is_object()?owner.find(key):nullptr;
}
// `str(value)` on the identities this module interpolates: an int keeps its decimal
// spelling and a string is itself.
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
// `site.get('uid', site['id'])` and `site.get('uid', str(site['id']))`: the two are not
// the same value when a site has no uid, and the reference uses both.
const Value& site_uid_or_id(const Value& site) {
    const Value* uid=find_field(site,"uid");
    return uid!=nullptr?*uid:site.at("id");
}
// `site.get('uid', str(site['id']))`: the value the record carries as `city_uid`, WITH
// ITS OWN TYPE. Only the FALLBACK is stringified, so a uid that is an int stays an int
// in the emitted record (`"city_uid":90210`, not `"90210"`), a float uid stays a float,
// and the value is compared against the threat table by Python `==`, where a string
// never equals a number. Stringifying it here made three separate wrong answers: the
// wrong JSON type, a threat row that silently missed, and a truncated junction id.
Value site_city_uid(const Value& site) {
    const Value* uid=find_field(site,"uid");
    return uid!=nullptr?*uid:vstr(py_str(site.at("id")));
}

// ---------------------------------------------------------------------------
// terrain_detail.HeightField, over the raw rasters rather than a world envelope.
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
// `{5:1.4,3:.8,4:1.,7:1.,15:.8}.get(code,.65)`.
//
// This is a dict lookup, not arithmetic. The reference never converts the cell to a
// number, so a raster whose cells are None, a string or a bool simply misses every key
// and takes the .65 default; converting instead refused the world outright and emitted
// no record where CPython emits a complete one. A float 5.0 hashes equal to the int 5,
// so the numeric keys still match numerically.
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
    // A list or a dict is unhashable, and dict.get raises rather than defaulting.
    if(code.kind==Value::Kind::Array) throw PlannerError("unhashable type: 'list'");
    if(code.kind==Value::Kind::Object) throw PlannerError("unhashable type: 'dict'");
    // None, a string and a bool are all hashable, and none of them is one of the keys
    // (hash(True) is hash(1), and 1 is not a key either).
    return .65;
}
// `v['biome'] in (4,7,15)`: three `==` tests, so a float 4.0 counts, a bool does not,
// and None or a string is simply not in the tuple.
bool wooded_code(const Value& code) {
    return value_equal(code,Value::make_int(4))||value_equal(code,Value::make_int(7))
        ||value_equal(code,Value::make_int(15));
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
    // `grid('natural_biome',3)`: the cells stay Python values, because the only thing
    // done with one is a dict lookup that copes with any hashable value.
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
// city_planner._sampler
// ---------------------------------------------------------------------------
struct SampleResult {
    bool water=false;
    double slope=0.,flood=0.,height=0.,moisture=0.;
    // `v['biome']` and `v['variant']` reach the record as the raster's own Python
    // values, which plan_city copies straight out of the layer; the only thing read off
    // the sample itself is the `in (4,7,15)` test, so that answer is carried here
    // rather than a number the cell may not have.
    bool wooded=false;
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
    const double span=static_cast<double>(n_-1);
    // `lat=math.pi/2-math.pi*site['z']/(n-1)` is the reference's first division by the
    // grid span, and HeightField (the member above, constructed first here as it is
    // there) performs none. A grid of size one therefore raises ZeroDivisionError right
    // here in CPython. Raising too is not defensive tidiness: letting the float
    // divisions run would carry infinities into the raster, and sample() would then
    // reach `% (n-1)` on integers, which on Windows is a hardware divide fault that
    // takes the whole process down with no catchable exception at all.
    if(span==0.) throw PlannerZeroDivision();
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
    // Note the reference does NOT clamp before asin here, unlike HeightField._cell.
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
    // An absent layer is the literal 3, which is not one of (4,7,15).
    out.wooded=world_->natural_biome.present&&wooded_code(world_->natural_biome.rows[gz][gx]);
    return out;
}

// ---------------------------------------------------------------------------
// Preset adapters: the fortification slice takes measured rows, the planner takes the
// whole catalogue dict, and both have to see the same rows.
// ---------------------------------------------------------------------------
std::int64_t staffing_target_sum(const Value& row) {
    const Value* staffing=find_field(row,"staffing");
    if(staffing==nullptr||!staffing->is_object()) return 0;
    const Value* roles=staffing->find("roles");
    if(roles==nullptr||!roles->is_array()) return 0;
    std::int64_t total=0;
    for(const Value& role:roles->items) total+=field_int(role,"target");
    return total;
}
FortificationPresetRow to_fortification_row(const Value& row) {
    FortificationPresetRow out;
    const Value* structure_id=find_field(row,"structure_id");
    if(structure_id!=nullptr&&structure_id->is_string()) out.structure_id=structure_id->text;
    const Value* id=find_field(row,"id");
    if(id!=nullptr&&id->is_string()) out.id=id->text;
    const Value* plot=find_field(row,"plot_m");
    if(plot!=nullptr) {out.plot_width=field_number(*plot,"width");out.plot_depth=field_number(*plot,"depth");}
    const Value* count=find_field(row,"count");
    if(count!=nullptr) out.count=as_number(*count);
    const Value* staffing=find_field(row,"staffing");
    if(staffing!=nullptr&&staffing->is_object()) {
        const Value* roles=staffing->find("roles");
        if(roles!=nullptr&&roles->is_array())
            for(const Value& role:roles->items) out.role_targets.push_back(field_number(role,"target"));
    }
    const Value* dimensions=find_field(row,"dimensions_m");
    if(dimensions!=nullptr&&dimensions->is_object()) {
        out.has_dimensions=true;
        out.width=field_number(*dimensions,"width");
        out.depth=field_number(*dimensions,"depth");
        out.height=field_number(*dimensions,"height");
    }
    return out;
}
FortificationPreset to_fortification_preset(const Value& preset) {
    FortificationPreset out;
    const Value* buildings=find_field(preset,"buildings");
    if(buildings!=nullptr)
        for(const Value& row:buildings->items) out.buildings.push_back(to_fortification_row(row));
    const Value* infrastructure=find_field(preset,"infrastructure");
    if(infrastructure!=nullptr)
        for(const Value& row:infrastructure->items) out.infrastructure.push_back(to_fortification_row(row));
    return out;
}
// The gatehouse row `wall_and_gate_defs` picks, as the catalogue dict itself. The
// fortification port hands back only the identity and the measured dimensions, and
// `install` needs the plot, the name and the staffing off the same row.
const Value* gate_preset_row(const Value& preset) {
    const Value* buildings=find_field(preset,"buildings");
    const Value* infrastructure=find_field(preset,"infrastructure");
    auto lookup=[](const Value* group,const std::string& id)->const Value* {
        const Value* found=nullptr;
        if(group!=nullptr)
            for(const Value& row:group->items) {
                const Value* structure_id=find_field(row,"structure_id");
                if(structure_id!=nullptr&&structure_id->is_string()&&structure_id->text==id) found=&row;
            }
        return found;
    };
    const Value* building=lookup(buildings,"building.gatehouse");
    return building!=nullptr?building:lookup(infrastructure,"building.gatehouse");
}
const Value* preset_row(const Value& preset,const std::string& structure_id) {
    const Value* buildings=find_field(preset,"buildings");
    if(buildings==nullptr) return nullptr;
    for(const Value& row:buildings->items) {
        const Value* id=find_field(row,"structure_id");
        if(id!=nullptr&&id->is_string()&&id->text==structure_id) return &row;
    }
    return nullptr;
}

// ---------------------------------------------------------------------------
// Adapters onto the accepted ports, and back into the emitted record.
// ---------------------------------------------------------------------------
// `site.get('uid', site['id'])` as sceneframe sees it.
//
// road_entries asks exactly two things of an identity: the str() spelling, which it
// interpolates into every junction id, and equality against the other sites. Identity
// holds an int or a string, so a float, a bool or a None uid has no faithful integer
// form -- coercing one truncated 2.5 to 2 and spelled the junction `junction:2:4` where
// the reference writes `junction:2.5:4`. Every value that is not an int is therefore
// carried as its str() spelling, which makes the label exact; the EQUALITY that could
// then confuse a float 2.5 with the string "2.5" is resolved in plan_city against the
// real Python values, before sceneframe ever sees the list.
sceneframe::Identity to_identity(const Value& value) {
    if(value.kind==Value::Kind::Int&&value.whole_fits) return sceneframe::identity_number(value.whole);
    return sceneframe::identity_text(py_str(value));
}
// CPython's sum() over a mixed numeric sequence: exact integer arithmetic until the
// first float, which is added to the running integer once, plainly, and then Neumaier
// compensation from there. The reference sums plot areas, which the shipped catalogues
// author as integers, but a measured float would change both the arithmetic and the
// type of the number the record carries.
class PySum {
  public:
    void add(const Value& term) {
        if(term.kind==Value::Kind::Int&&term.whole_fits&&integral_) {whole_+=term.whole;return;}
        add_double(as_number(term),term.kind==Value::Kind::Int);
    }
    void add_product(const Value& a,const Value& b) {
        if(a.kind==Value::Kind::Int&&b.kind==Value::Kind::Int&&a.whole_fits&&b.whole_fits&&integral_) {
            whole_+=a.whole*b.whole;return;
        }
        add_double(as_number(a)*as_number(b),a.kind==Value::Kind::Int&&b.kind==Value::Kind::Int);
    }
    Value value() const {
        return integral_?Value::make_int(whole_):Value::make_float(total_+compensation_);
    }
  private:
    void add_double(double x,bool still_integral) {
        if(integral_&&still_integral) {whole_+=static_cast<std::int64_t>(x);return;}
        if(integral_) {
            integral_=false;
            total_=static_cast<double>(whole_)+x;   // the one plain PyNumber_Add
            compensation_=0.;
            return;
        }
        const double t=total_+x;
        if(std::fabs(total_)>=std::fabs(x)) compensation_+=(total_-t)+x;
        else compensation_+=(x-t)+total_;
        total_=t;
    }
    bool integral_=true;
    std::int64_t whole_=0;
    double total_=0.,compensation_=0.;
};
// The key order of one shape's `layout` dict, as the catalogue file spells it.
//
// The shape port normalizes `layout` into a sorted map because nothing it computes
// depends on the order. The emitted record does: it carries the Python dict straight
// through, so `footprint` has to come before `street_network`. Recovered by reading the
// same catalogue file the shape port hashed, which is the only authority for it.
const std::vector<std::string>& layout_order(const std::string& shape_id) {
    static std::string cached_path;
    static std::map<std::string,std::vector<std::string>> cached;
    static const std::vector<std::string> none;
    const std::string& path=cityshapes::catalogue_path();
    if(path!=cached_path) {
        cached.clear();
        std::ifstream file(path,std::ios::binary);
        std::ostringstream buffer;
        buffer<<file.rdbuf();
        const Value document=settlementpresets::loads(buffer.str());
        const Value* shapes=find_field(document,"shapes");
        if(shapes!=nullptr)
            for(const Value& shape:shapes->items) {
                const Value* id=find_field(shape,"id");
                const Value* layout=find_field(shape,"layout");
                if(id==nullptr||!id->is_string()||layout==nullptr) continue;
                std::vector<std::string> keys;
                for(const auto& entry:layout->fields) keys.push_back(entry.first);
                cached.emplace(id->text,std::move(keys));
            }
        cached_path=path;
    }
    auto found=cached.find(shape_id);
    return found!=cached.end()?found->second:none;
}
Value selection_value(const cityshapes::Selection& selected) {
    Value out=vobj();
    out.set("version",vint(selected.version));
    out.set("catalogue_revision",vint(selected.catalogue_revision));
    out.set("catalogue_sha256",vstr(selected.catalogue_sha256));
    out.set("shape_id",selected.has_shape?vstr(selected.shape_id):Value::make_null());
    Value parameters=vobj();
    // `for key, interval in sorted(shape['variation'].items())`, so a sorted map is the
    // reference's own order here.
    for(const auto& entry:selected.parameters)
        parameters.set(entry.first,entry.second.integer?vint(entry.second.whole)
                                                       :vflt(entry.second.real));
    out.set("parameters",std::move(parameters));
    Value candidates=varr();
    for(const cityshapes::Candidate& candidate:selected.candidates) {
        Value item=vobj();
        item.set("id",vstr(candidate.id));
        item.set("family",vstr(candidate.family));
        item.set("weight",vflt(candidate.weight));
        Value matched=varr();
        for(const std::string& field:candidate.matched_preferences) matched.items.push_back(vstr(field));
        item.set("matched_preferences",std::move(matched));
        candidates.items.push_back(std::move(item));
    }
    out.set("candidates",std::move(candidates));
    out.set("runtime_geometry_generated",vbool(selected.runtime_geometry_generated));
    if(!selected.has_shape) {out.set("reason",vstr(selected.reason));return out;}
    Value layout=vobj();
    for(const std::string& key:layout_order(selected.shape_id)) {
        auto found=selected.layout.find(key);
        if(found!=selected.layout.end()) layout.set(key,vstr(found->second));
    }
    for(const auto& entry:selected.layout)
        if(layout.find(entry.first)==nullptr) layout.set(entry.first,vstr(entry.second));
    out.set("layout",std::move(layout));
    Value sources=varr();
    for(const std::string& id:selected.source_ids) sources.items.push_back(vstr(id));
    out.set("source_ids",std::move(sources));
    out.set("reason",vstr(selected.reason));
    return out;
}
Value fortifications_value(const FortificationReport& report) {
    Value out=vobj();
    out.set("version",vint(report.version));
    out.set("defended_perimeter",vbool(report.defended_perimeter));
    Value rings=varr();
    for(const FortificationRing& ring:report.rings) {
        Value item=vobj();
        item.set("id",vstr(ring.id));
        item.set("role",vstr(ring.role));
        item.set("scale",vflt(ring.scale));
        Value polyline=varr();
        for(const auto& point:ring.polyline_m) polyline.items.push_back(vpair(point.first,point.second));
        item.set("polyline_m",std::move(polyline));
        item.set("status",vstr(ring.status));
        item.set("segment_count",vint(ring.segment_count));
        item.set("gate_count",vint(ring.gate_count));
        rings.items.push_back(std::move(item));
    }
    out.set("rings",std::move(rings));
    Value segments=varr();
    for(const FortificationSegment& segment:report.segments) {
        Value item=vobj();
        item.set("id",vstr(segment.id));
        item.set("ring_id",vstr(segment.ring_id));
        item.set("structure_id",vstr(segment.structure_id));
        item.set("from_m",vpair(segment.from_m.first,segment.from_m.second));
        item.set("to_m",vpair(segment.to_m.first,segment.to_m.second));
        item.set("center_m",vpair(segment.center_m.first,segment.center_m.second));
        item.set("length_m",vflt(segment.length_m));
        item.set("rotation_degrees",vflt(segment.rotation_degrees));
        segments.items.push_back(std::move(item));
    }
    out.set("segments",std::move(segments));
    Value nodes=varr();
    for(const FortificationNode& node:report.nodes) {
        Value item=vobj();
        item.set("id",vstr(node.id));
        item.set("kind",vstr(node.kind));
        item.set("position_m",vpair(node.position_m.first,node.position_m.second));
        item.set("ring_id",vstr(node.ring_id));
        nodes.items.push_back(std::move(item));
    }
    out.set("nodes",std::move(nodes));
    Value gates=varr();
    for(const FortificationGate& gate:report.gates) {
        Value item=vobj();
        item.set("id",vstr(gate.id));
        item.set("ring_id",vstr(gate.ring_id));
        item.set("structure_id",vstr(gate.structure_id));
        item.set("position_m",vpair(gate.position_m.first,gate.position_m.second));
        item.set("approach_m",vpair(gate.approach_m.first,gate.approach_m.second));
        item.set("route_index",gate.has_route_index?vint(gate.route_index):Value::make_null());
        gates.items.push_back(std::move(item));
    }
    out.set("gates",std::move(gates));
    Value towers=varr();
    for(const FortificationTower& tower:report.towers) {
        Value item=vobj();
        item.set("id",vstr(tower.id));
        item.set("ring_id",vstr(tower.ring_id));
        item.set("structure_id",vstr(tower.structure_id));
        item.set("position_m",vpair(tower.position_m.first,tower.position_m.second));
        towers.items.push_back(std::move(item));
    }
    out.set("towers",std::move(towers));
    Value unplaced=varr();
    for(const FortificationUnplaced& row:report.unplaced) {
        Value item=vobj();
        item.set("building_id",vstr(row.building_id));
        if(row.has_ring_id) item.set("ring_id",vstr(row.ring_id));
        item.set("reason",vstr(row.reason));
        unplaced.items.push_back(std::move(item));
    }
    out.set("unplaced",std::move(unplaced));
    out.set("method",vstr(report.method));
    out.set("limits",vstr(report.limits));
    return out;
}

// ---------------------------------------------------------------------------
// Packing state
// ---------------------------------------------------------------------------
using CellVec=std::vector<Cell>;
CellVec to_vector(const std::set<Cell>& cells) {return CellVec(cells.begin(),cells.end());}
bool intersects(const CellVec& cells,const std::set<Cell>& other) {
    for(const Cell& c:cells) if(other.count(c)!=0) return true;
    return false;
}
bool subset(const CellVec& cells,const std::set<Cell>& other) {
    for(const Cell& c:cells) if(other.count(c)==0) return false;
    return true;
}
// One street-front alternative: the reference's
// (x, z, degrees, ax, az, footprint, corridor, ground) tuple.
//
// `ground` is reduced to its extremes because the reference only ever reads max() and
// min() of it -- the comment at city_planner.py:192 says exactly that -- and two
// options with the same geometry necessarily have the same list anyway, so tuple
// equality, which `housing_reserve.remove` needs, is unaffected.
struct Option {
    double x=0.,z=0.,degrees=0.,ax=0.,az=0.;
    CellVec footprint;
    std::size_t corridor=0;
    double ground_min=0.,ground_max=0.;
};

struct Packer {
    const World* world=nullptr;
    const Sampler* sampler=nullptr;
    std::int64_t half=0;
    const std::set<Cell>* valid=nullptr;
    const std::set<Cell>* road=nullptr;
    const std::map<Cell,double>* heights=nullptr;
    const std::vector<std::array<double,3>>* anchors=nullptr;
    std::vector<CellVec> corridor_pool;
    std::map<std::array<double,4>,std::size_t> corridor_cache;
    std::map<std::pair<double,double>,std::vector<Option>> candidate_cache;
    std::set<Cell> occupied,access,reserved;
    std::vector<const Option*> housing_reserve;

    std::set<Cell> cells(double x,double z,double w,double d,double angle=0.) const {
        return footprint_cells(x,z,w,d,angle,static_cast<double>(half),
                               static_cast<double>(planner_cell));
    }
    const std::vector<Option>& candidates(double w,double d);
    std::int64_t free_frontage(double w,double d);
    bool option_equal(const Option& a,const Option& b) const {
        if(&a==&b) return true;
        return a.x==b.x&&a.z==b.z&&a.degrees==b.degrees&&a.ax==b.ax&&a.az==b.az
            &&a.footprint==b.footprint&&corridor_pool[a.corridor]==corridor_pool[b.corridor]
            &&a.ground_min==b.ground_min&&a.ground_max==b.ground_max;
    }
};
const std::vector<Option>& Packer::candidates(double w,double d) {
    const std::pair<double,double> key(w,d);
    auto cached=candidate_cache.find(key);
    if(cached!=candidate_cache.end()) return cached->second;
    std::vector<Option> options;
    const double grade_limit=python_hypot(w,d)*std::tan(py_radians(25));
    for(const std::array<double,3>& anchor:*anchors) {
        const double ax=anchor[0],az=anchor[1];
        double angle=anchor[2];
        for(int side=1;side>=-1;side-=2) {
            const double dx=-std::sin(angle)*side,dz=std::cos(angle)*side;
            const double x=round_to(ax+dx*(d/2+10),2),z=round_to(az+dz*(d/2+10),2);
            // The reference rebinds `angle` here, inside the `for side` loop, so the
            // second side of every anchor is laid out from the ROUNDED heading rather
            // than from the anchor's own. Reproduced deliberately.
            const double degrees=round_to(py_degrees(angle),4);
            angle=py_radians(degrees);
            const CellVec footprint=to_vector(cells(x,z,w,d,angle));
            if(!subset(footprint,*valid)||intersects(footprint,*road)) continue;
            // The interpolated ground under the corners, plus the raster cells the
            // plot covers. Only the extremes are ever read.
            double ground_min=0.,ground_max=0.;
            bool first=true;
            auto observe=[&](double value) {
                if(first) {ground_min=ground_max=value;first=false;return;}
                ground_min=std::min(ground_min,value);ground_max=std::max(ground_max,value);
            };
            for(const auto& corner:corners(x,z,w,d,angle))
                observe(sampler->sample(corner.first,corner.second,false).height);
            for(const Cell& c:footprint) observe(heights->at(c));
            if(ground_max-ground_min>grade_limit) continue;
            const double ex=x-dx*d/2,ez=z-dz*d/2;
            const std::array<double,4> corridor_key{ax,az,ex,ez};
            auto found=corridor_cache.find(corridor_key);
            std::size_t corridor_index=0;
            if(found!=corridor_cache.end()) corridor_index=found->second;
            else {
                std::set<Cell> corridor;
                for(int t=0;t<11;++t) {
                    const std::set<Cell> step=cells(ax+(ex-ax)*t/10,az+(ez-az)*t/10,4,4);
                    corridor.insert(step.begin(),step.end());
                }
                corridor_index=corridor_pool.size();
                corridor_pool.push_back(to_vector(corridor));
                corridor_cache.emplace(corridor_key,corridor_index);
            }
            if(!subset(corridor_pool[corridor_index],*valid)) continue;
            Option option;
            option.x=x;option.z=z;option.degrees=degrees;option.ax=ax;option.az=az;
            option.footprint=footprint;option.corridor=corridor_index;
            option.ground_min=ground_min;option.ground_max=ground_max;
            options.push_back(std::move(option));
        }
    }
    return candidate_cache.emplace(key,std::move(options)).first->second;
}
std::int64_t Packer::free_frontage(double w,double d) {
    std::int64_t total=0;
    for(const Option& option:candidates(w,d)) {
        const CellVec& corridor=corridor_pool[option.corridor];
        if(intersects(option.footprint,occupied)||intersects(option.footprint,access)
           ||intersects(corridor,occupied)||intersects(option.footprint,reserved)
           ||intersects(corridor,reserved)) continue;
        ++total;
    }
    return total;
}
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
    out.set("shapes_sha256",vstr(cityshapes::load_catalogue().identity()));
    return out;
}

Value plan_city(const World& world,const Value& site,
                const std::map<std::string,std::int64_t>& nearby_counts) {
    const std::string city_class=site.at("city_class").text;
    const Value preset=settlementpresets::city_plan(site.at("population_profile").text,
                                                    city_class+"_city");
    const Value housing=settlementpresets::section("housing_profiles");
    const Value& house=housing.at("worker_house");
    const Value& apartment=housing.at("worker_apartment");
    const std::int64_t n=world.size;
    const double span=static_cast<double>(n-1);
    const double radius=world.globe_radius;
    // Bound footprints by neighbouring city anchors, without moving any anchor.
    double neighbour_half=0.;
    if(city_class=="small") neighbour_half=240.;
    else if(city_class=="medium") neighbour_half=320.;
    else if(city_class=="capital") neighbour_half=400.;
    else throw PlannerError("'"+city_class+"'");    // the reference's KeyError
    const Value* site_uid=find_field(site,"uid");
    const double site_x=field_number(site,"x"),site_z=field_number(site,"z");
    const Value missing=Value::make_null();
    for(const Value& other:world.sites) {
        // `other is site or other.get('uid')==site.get('uid')`: identity first, then the
        // uid, so two sites that both lack one are the same settlement to the reference.
        if(&other==&site) continue;
        const Value* other_uid=find_field(other,"uid");
        if(value_equal(other_uid!=nullptr?*other_uid:missing,site_uid!=nullptr?*site_uid:missing))
            continue;
        // `math.pi*site['z']/(n-1)`: with a grid of size one the span is zero and
        // CPython raises here, before any coordinate exists.
        if(span==0.) throw PlannerZeroDivision();
        const double lat1=pi/2-pi*site_z/span;
        const double lat2=pi/2-pi*field_number(other,"z")/span;
        const double dl=2*pi*(field_number(other,"x")-site_x)/span;
        const double cosine=std::sin(lat1)*std::sin(lat2)+std::cos(lat1)*std::cos(lat2)*std::cos(dl);
        const double distance=radius*std::acos(std::max(-1.,std::min(1.,cosine)));
        neighbour_half=std::min(neighbour_half,distance*.28);
    }
    const FortificationPreset fortification_preset=to_fortification_preset(preset);
    const Value& house_plot=house.at("plot_m");
    const std::int64_t half=program_half_m(fortification_preset,city_class,neighbour_half,
                                           field_number(house_plot,"width"),
                                           field_number(house_plot,"depth"),
                                           field_int(house,"worker_beds"));
    const std::int64_t size=floor_div(2*half,planner_cell);
    const Sampler sampler(world,site,static_cast<double>(half));
    const double resolution=sampler.resolution();
    const double half_m=static_cast<double>(half);
    const double cell_m=static_cast<double>(planner_cell);

    Value terrain_codes=varr(),terrain_biomes=varr(),terrain_variants=varr();
    std::set<Cell> valid;
    Sum slope_total;
    std::int64_t slope_count=0,woods=0;
    std::map<Cell,double> heights;
    for(std::int64_t j=0;j<size;++j) {
        Value row=varr(),biome_row=varr(),mutation_row=varr();
        for(std::int64_t i=0;i<size;++i) {
            const SampleResult v=sampler.sample(-half_m+(static_cast<double>(i)+.5)*cell_m,
                                                -half_m+(static_cast<double>(j)+.5)*cell_m);
            heights.emplace(Cell(i,j),v.height);
            const std::int64_t code=v.water?1:(v.slope>25||v.flood>.65?2:0);
            row.items.push_back(vint(code));
            const auto gx=static_cast<std::size_t>(v.gx);
            const auto gz=static_cast<std::size_t>(v.gz);
            biome_row.items.push_back(world.natural_biome.present
                ?world.natural_biome.rows[gz][gx]:vint(3));
            mutation_row.items.push_back(world.biome_variant.present
                ?world.biome_variant.rows[gz][gx]:vint(-1));
            if(code==0) {
                valid.emplace(i,j);
                // sum(slopes)/len(slopes): a float sum, so Neumaier compensated.
                slope_total.add(v.slope);++slope_count;
                if(v.wooded) ++woods;
            }
        }
        terrain_codes.items.push_back(std::move(row));
        terrain_biomes.items.push_back(std::move(biome_row));
        terrain_variants.items.push_back(std::move(mutation_row));
    }
    const std::int64_t surface_size=size+1;
    Value surface=vobj();
    surface.set("size",vint(surface_size));
    surface.set("step_m",vflt(static_cast<double>(2*half)/static_cast<double>(surface_size-1)));
    Value heights_m=varr();
    for(std::int64_t j=0;j<surface_size;++j) {
        Value row=varr();
        for(std::int64_t i=0;i<surface_size;++i) {
            // i*2*half is an exact integer product in the reference, divided only once.
            const double sx=-half_m+static_cast<double>(i*2*half)/static_cast<double>(surface_size-1);
            const double sz=-half_m+static_cast<double>(j*2*half)/static_cast<double>(surface_size-1);
            row.items.push_back(vflt(round_to(sampler.sample(sx,sz,false).height,4)));
        }
        heights_m.items.push_back(std::move(row));
    }
    surface.set("heights_m",std::move(heights_m));
    surface.set("source",vstr("canonical terrain height in metres"));
    surface.set("terrain_detail",world.has_terrain_detail?world.terrain_detail:Value::make_null());
    surface.set("coordinates",vstr("local east/north gnomonic coordinates; radial elevation above reference sphere"));
    const SampleResult center=sampler.sample(0,0);
    // The record's own `city_uid`, with its Python type intact, and the f-string
    // spelling of it that the streets seed interpolates.
    const Value city_uid_value=site_city_uid(site);
    const std::string city_uid=py_str(city_uid_value);
    // `next((c['regional_threat'] for c in ... if c['city_uid']==site.get('uid',str(site['id']))),0.)`
    // -- Python `==` on the raw values. A string-keyed row cannot match a numeric uid.
    Value threat=vflt(0.);
    if(!world.threat_rows.empty()) {
        for(const auto& entry:world.threat_rows)
            if(value_equal(entry.first,city_uid_value)) {threat=entry.second;break;}
    } else {
        for(const auto& entry:world.threat_cities)
            if(value_equal(vstr(entry.first),city_uid_value)) {threat=entry.second;break;}
    }

    const auto valid_count=static_cast<std::int64_t>(valid.size());
    Value facts=vobj();
    facts.set("buildable_area_m2",vint(valid_count*planner_cell*planner_cell));
    facts.set("usable_land_fraction",vflt(static_cast<double>(valid_count)/static_cast<double>(size*size)));
    facts.set("local_slope_degrees",slope_count!=0
        ?vflt(slope_total.value()/static_cast<double>(slope_count)):vint(90));
    // 1-max(0,min(1,moisture)): both clamps are Python ints, so a saturated moisture
    // makes aridity an int and json.dumps writes `0` rather than `0.0`.
    const double moisture=center.moisture;
    facts.set("aridity",moisture>=1.?vint(0):(moisture<=0.?vint(1):vflt(1-moisture)));
    facts.set("wooded_fraction",vflt(static_cast<double>(woods)
        /static_cast<double>(std::max<std::int64_t>(1,valid_count))));
    facts.set("regional_threat",threat);
    facts.set("defense_priority",threat);

    cityshapes::Site shape_site;
    for(const auto& entry:facts.fields)
        shape_site.emplace_back(entry.first,cityshapes::site_number(as_number(entry.second)));
    const cityshapes::Selection selected=cityshapes::select_shape(
        shape_site,world.seed,py_str(site_uid_or_id(site)),city_class,nearby_counts);

    Value result=vobj();
    result.set("version",vint(planner_version));
    result.set("city_uid",city_uid_value);
    result.set("site_id",site.at("id"));
    result.set("name",site.at("name"));
    result.set("civilization_id",site.at("population_profile"));
    result.set("city_class",vstr(city_class));
    result.set("unit",vstr("metres"));
    Value bounds=varr();
    bounds.items.push_back(vint(-half));bounds.items.push_back(vint(-half));
    bounds.items.push_back(vint(half));bounds.items.push_back(vint(half));
    result.set("bounds_m",std::move(bounds));
    Value terrain=vobj();
    terrain.set("cell_m",vint(planner_cell));
    terrain.set("size",vint(size));
    terrain.set("codes",std::move(terrain_codes));
    terrain.set("surface",std::move(surface));
    terrain.set("natural_biome",std::move(terrain_biomes));
    terrain.set("biome_variant",std::move(terrain_variants));
    terrain.set("biome_catalogue",world.biome_catalogue.is_array()?world.biome_catalogue:varr());
    terrain.set("magical_catalogue",world.magical_catalogue.is_array()?world.magical_catalogue:varr());
    Value magic_colors=vobj();
    for(const auto& entry:world.magic_colors) magic_colors.set(entry.first,entry.second);
    terrain.set("magic_colors",std::move(magic_colors));
    result.set("terrain",std::move(terrain));
    Value frame=vobj();
    frame.set("radius_m",world.radius);
    frame.set("latitude_degrees",vflt(90-180*site_z/span));
    frame.set("longitude_degrees",vflt(-180+360*site_x/span));
    frame.set("projection",vstr("direction=normalize(up+(east*x_m+north*z_m)/radius_m); position=(radius_m+height_m)*direction"));
    result.set("reference_frame",std::move(frame));
    result.set("location",facts);
    result.set("shape",selection_value(selected));
    result.set("plots",varr());
    result.set("roads",varr());
    result.set("unplaced",varr());
    result.set("fortifications",Value::make_null());
    Value passes=varr();
    static const char* phase_ids[]={"map","shape","fortification","high","high_housing","low","low_housing"};
    for(const char* key:phase_ids) {
        Value pass=vobj();pass.set("id",vstr(key));pass.set("placed",vint(0));
        passes.items.push_back(std::move(pass));
    }
    result.set("passes",std::move(passes));
    Value warnings=varr();
    warnings.items.push_back(vstr("Schematic packing over canonical detailed terrain; groundwater and structural feasibility are not resolved."));
    warnings.items.push_back(vstr("Routed river centerlines reserve a provisional 24 m channel and 28 m setback from centerline, not a simulated flood extent."));
    warnings.items.push_back(vstr("Four worker beds per house; 16 per apartment building when land is constrained. Dependents, commuters and households are not modeled."));
    warnings.items.push_back(vstr("City walls are schematic enceintes separate from castle bailey generation."));
    result.set("warnings",std::move(warnings));
    result.set("source_resolution_m",vflt(round_to(resolution,2)));
    result.set("status",vstr("unbuildable"));
    result.set("stats",vobj());
    Value debug=vobj();
    debug.set("terrain_safe_cells",vint(valid_count));
    debug.set("total_cells",vint(size*size));
    debug.set("housing_passes",varr());
    debug.set("apartment_policy",vstr("houses_first_then_upgrade_on_plot_exhaustion"));
    result.set("debug",std::move(debug));

    // world_scene.road_entries, over the same world slice.
    sceneframe::World scene_world;
    scene_world.size=n;
    scene_world.config_globe_radius=radius;
    scene_world.has_effective_config=false;
    scene_world.water_nodes=world.water_nodes;
    scene_world.routes=world.routes;
    sceneframe::Site scene_site;
    scene_site.x=site_x;scene_site.z=site_z;scene_site.id=to_identity(site_uid_or_id(site));
    {
        // `site_index=next((i for i,s in enumerate(sites) if s.get('uid',s['id'])==
        //                   site.get('uid',site['id'])),None)`
        //
        // Resolved here, on the real Python values, because sceneframe::Identity cannot
        // tell a float 2.5 from the string "2.5" and road_entries would then match the
        // wrong row. The list handed over reproduces exactly this answer: the matched
        // row carries this site's identity and every other row is built to be unequal
        // to it, so sceneframe's own scan lands on the same index -- or, when nothing
        // matched, on nothing, which is the reference's None.
        const Value& wanted=site_uid_or_id(site);
        std::size_t matched=world.sites.size();
        for(std::size_t i=0;i<world.sites.size();++i)
            if(value_equal(site_uid_or_id(world.sites[i]),wanted)) {matched=i;break;}
        const sceneframe::Identity other=scene_site.id.is_text
            ?sceneframe::identity_number(0):sceneframe::identity_text(std::string());
        for(std::size_t i=0;i<world.sites.size();++i)
            scene_world.site_ids.push_back(i==matched?scene_site.id:other);
    }
    const std::vector<sceneframe::RoadEntry> road_entries=
        sceneframe::road_entries(scene_world,scene_site,half_m);
    Value connections=varr();
    for(const sceneframe::RoadEntry& entry:road_entries) {
        Value item=vobj();
        item.set("route_id",vstr(entry.route_id));
        item.set("route_index",vint(entry.route_index));
        item.set("end",vstr(entry.end));
        item.set("outside_index",vint(entry.outside_index));
        item.set("junction_id",vstr(entry.junction_id));
        item.set("gate_local_m",vpair(entry.gate_local_m[0],entry.gate_local_m[1]));
        Value dir=varr();
        for(double v:entry.direction) dir.items.push_back(vflt(v));
        item.set("direction",std::move(dir));
        item.set("status",vstr(entry.status));
        item.set("reason",vstr(entry.reason));
        connections.items.push_back(std::move(item));
    }
    result.set("road_connections",std::move(connections));
    if(resolution>half_m)
        result.find("warnings")->items.push_back(vstr("Regional land categories repeat coarse samples; canonical local relief supplies finer elevation detail."));

    if(!selected.has_shape) {
        Value unplaced=varr();
        const Value* buildings=find_field(preset,"buildings");
        if(buildings!=nullptr)
            for(const Value& row:buildings->items) {
                Value item=vobj();
                item.set("building_id",row.at("structure_id"));
                item.set("count",row.at("count"));
                item.set("reason",vstr("No compatible buildable footprint"));
                unplaced.items.push_back(std::move(item));
            }
        result.set("unplaced",std::move(unplaced));
        Value stats=vobj();
        stats.set("workers",vint(0));
        stats.set("worker_beds",vint(0));
        stats.set("housing_shortfall",vint(0));
        stats.set("service_buildings",vint(0));
        stats.set("houses",vint(0));
        result.set("stats",std::move(stats));
        return result;
    }
    result.set("street_paths_m",varr());
    // No new keys are added to `result` past this point, so its field vector is stable.
    std::array<std::int64_t,7> placed{};
    placed[0]=valid_count;
    placed[1]=1;
    const std::string family=cityshapes::load_catalogue().family(selected.shape_id);
    const auto parameter=[&](const char* key,double fallback,bool* present=nullptr) {
        auto found=selected.parameters.find(key);
        if(found==selected.parameters.end()) {if(present!=nullptr)*present=false;return fallback;}
        if(present!=nullptr)*present=true;
        return found->second.value();
    };
    const double spacing=std::max(72.,parameter("block_spacing_m",0.));
    const double aspect=parameter("aspect_ratio",0.);
    const double rx=half_m*.94,rz=half_m*.94/std::min(aspect,2.);
    const double cluster_radius=std::pow(half_m*.52,2.);
    auto inside=[&](double x,double z) {
        if(family=="grid"||family=="compound"||family=="hybrid")
            return std::fabs(x)<rx&&std::fabs(z)<rz;
        if(family=="cluster") {
            const double centres[3][2]={{-half_m*.32,0.},{half_m*.32,0.},{0.,half_m*.25}};
            for(const auto& c:centres)
                if(std::pow(x-c[0],2.)+std::pow(z-c[1],2.)<cluster_radius) return true;
            return false;
        }
        // organic, contour, rings and paired lobes share an elliptical clip.
        return std::pow(x/rx,2.)+std::pow(z/rz,2.)<1;
    };
    const std::set<Cell> terrain_valid=valid;
    {
        std::set<Cell> clipped;
        for(const Cell& c:valid)
            if(inside(-half_m+(static_cast<double>(c.first)+.5)*cell_m,
                      -half_m+(static_cast<double>(c.second)+.5)*cell_m)) clipped.insert(c);
        valid=std::move(clipped);
    }
    const std::string digest=sha256(std::to_string(world.seed)+":"+city_uid+":streets-v2");
    const std::uint64_t street_seed=std::strtoull(digest.substr(0,16).c_str(),nullptr,16);
    Value& connection_list=*result.find("road_connections");
    std::vector<Cell> connection_cells;
    for(Value& entry:connection_list.items) {
        const Value& gate=entry.at("gate_local_m");
        Value cell_value=varr();
        Cell cell(0,0);
        for(int k=0;k<2;++k) {
            const double v=as_number(gate.items[static_cast<std::size_t>(k)]);
            const std::int64_t index=std::max<std::int64_t>(0,std::min<std::int64_t>(
                size-1,static_cast<std::int64_t>(std::floor((v+half_m)/cell_m))));
            cell_value.items.push_back(vint(index));
            (k==0?cell.first:cell.second)=index;
        }
        entry.set("cell",std::move(cell_value));
        connection_cells.push_back(cell);
    }
    const RoadNetwork network=grow_roads(connection_cells.empty()?valid:terrain_valid,heights,size,
                                         street_seed,spacing/cell_m,connection_cells);
    const std::set<Cell>& road=network.roads;
    for(std::size_t index=0;index<connection_list.items.size();++index) {
        Value& entry=connection_list.items[index];
        const Cell cell=connection_cells[index];
        const Value& gate=entry.at("gate_local_m");
        const double gx=as_number(gate.items[0]),gz=as_number(gate.items[1]);
        const double px=-half_m+(static_cast<double>(cell.first)+.5)*cell_m;
        const double pz=-half_m+(static_cast<double>(cell.second)+.5)*cell_m;
        const SampleResult v=sampler.sample(gx,gz);
        const double length=point_distance(px,pz,gx,gz);
        if(road.count(cell)!=0&&!v.water&&v.flood<=.65&&v.slope<=25
           &&std::fabs(v.height-heights.at(cell))<=.35*length+1e-6) {
            entry.set("status",vstr("connected"));
            entry.set("reason",vstr("Terrain-safe junction to regional road"));
            const std::vector<Cell>* approach=nullptr;
            for(const std::vector<Cell>& path:network.paths)
                if(!path.empty()&&path.back()==cell) {approach=&path;break;}
            Value local_path=varr();
            if(approach!=nullptr)
                for(const Cell& c:*approach)
                    local_path.items.push_back(vpair(-half_m+(static_cast<double>(c.first)+.5)*cell_m,
                                                     -half_m+(static_cast<double>(c.second)+.5)*cell_m));
            else
                local_path.items.push_back(vpair(-half_m+(static_cast<double>(cell.first)+.5)*cell_m,
                                                 -half_m+(static_cast<double>(cell.second)+.5)*cell_m));
            local_path.items.push_back(vpair(gx,gz));
            entry.set("local_path_m",std::move(local_path));
        }
    }
    {
        Value roads=varr();
        for(const Cell& c:road) {
            Value item=varr();
            item.items.push_back(vint(c.first));item.items.push_back(vint(c.second));
            roads.items.push_back(std::move(item));
        }
        result.set("roads",std::move(roads));
    }
    std::vector<std::vector<std::pair<double,double>>> street_paths;
    {
        Value paths=varr();
        for(const std::vector<Cell>& path:network.paths) {
            Value item=varr();
            std::vector<std::pair<double,double>> points;
            for(const Cell& c:path) {
                const double x=round_to(-half_m+(static_cast<double>(c.first)+.5)*cell_m,2);
                const double z=round_to(-half_m+(static_cast<double>(c.second)+.5)*cell_m,2);
                points.emplace_back(x,z);
                item.items.push_back(vpair(x,z));
            }
            street_paths.push_back(std::move(points));
            paths.items.push_back(std::move(item));
        }
        result.set("street_paths_m",std::move(paths));
    }

    const std::pair<FortificationStructure,FortificationStructure> defs=
        wall_and_gate_defs(fortification_preset);
    const FortificationStructure& wall_def=defs.first;
    const FortificationStructure& gate_def=defs.second;
    const Value* gate_row=gate_preset_row(preset);
    const Value* gate_count_row=preset_row(preset,"building.gatehouse");
    const Value* tower_count_row=preset_row(preset,"building.tower");
    const std::int64_t gate_budget=gate_count_row!=nullptr?field_int(*gate_count_row,"count"):0;
    const std::int64_t tower_budget=tower_count_row!=nullptr?field_int(*tower_count_row,"count"):0;
    std::vector<FortificationRoadConnection> fort_connections;
    for(const Value& entry:connection_list.items) {
        FortificationRoadConnection conn;
        conn.status=entry.at("status").text;
        const Value& gate=entry.at("gate_local_m");
        conn.has_gate=!gate.items.empty();
        if(conn.has_gate) conn.gate_local_m={as_number(gate.items[0]),as_number(gate.items[1])};
        conn.has_route_index=true;
        conn.route_index=entry.at("route_index").whole;
        fort_connections.push_back(conn);
    }
    FortificationShapeParameters shape_parameters;
    bool has_ring_count=false;
    const double ring_count=parameter("ring_count",0.,&has_ring_count);
    shape_parameters.has_ring_count=has_ring_count;
    shape_parameters.ring_count=ring_count;
    const FortificationReport fortifications=build_fortifications(
        valid,half_m,cell_m,rx,rz,family,selected.shape_id,shape_parameters,city_class,
        fort_connections,wall_def,gate_def,tower_budget,std::max<std::int64_t>(1,gate_budget));
    result.set("fortifications",fortifications_value(fortifications));
    placed[2]=static_cast<std::int64_t>(fortifications.segments.size());

    // Stable frontage variation follows the street, with modest organic deviations.
    std::vector<std::array<double,3>> anchors;
    {
        std::set<std::array<double,3>> seen;
        std::vector<std::array<double,3>> ordered;
        const auto wobble=static_cast<double>(street_seed%1000u);
        for(const std::vector<std::pair<double,double>>& path:street_paths) {
            const auto count=static_cast<std::int64_t>(path.size());
            for(std::int64_t i=0;i<count;++i) {
                const std::pair<double,double>& a=path[static_cast<std::size_t>(std::max<std::int64_t>(0,i-3))];
                const std::pair<double,double>& b=path[static_cast<std::size_t>(std::min<std::int64_t>(count-1,i+3))];
                if(a==b) continue;
                const double x=path[static_cast<std::size_t>(i)].first;
                const double z=path[static_cast<std::size_t>(i)].second;
                double angle=std::atan2(b.second-a.second,b.first-a.first);
                angle+=py_radians(5*std::sin(x*.13+z*.17+wobble));
                const std::array<double,3> anchor{x,z,angle};
                if(seen.insert(anchor).second) ordered.push_back(anchor);
            }
        }
        anchors=std::move(ordered);
        // sorted(set(anchors), key=lambda p:(p[0]**2+p[1]**2, p)). The key is total, so
        // the set's own order never shows and a plain sort is enough.
        std::stable_sort(anchors.begin(),anchors.end(),
            [](const std::array<double,3>& a,const std::array<double,3>& b) {
                const double ra=std::pow(a[0],2.)+std::pow(a[1],2.);
                const double rb=std::pow(b[0],2.)+std::pow(b[1],2.);
                if(ra!=rb) return ra<rb;
                return a<b;
            });
    }

    Packer packer;
    packer.world=&world;packer.sampler=&sampler;packer.half=half;
    packer.valid=&valid;packer.road=&road;packer.heights=&heights;packer.anchors=&anchors;

    // ---- install --------------------------------------------------------------
    auto install=[&](const Value& row,const std::string& phase,const std::string& kind,
                     const Option* placement)->bool {
        const Value& plot_m=row.at("plot_m");
        const double w=field_number(plot_m,"width"),d=field_number(plot_m,"depth");
        const std::vector<Option> single;
        const std::vector<Option>& pool=placement!=nullptr?single:packer.candidates(w,d);
        const std::size_t total=placement!=nullptr?1:pool.size();
        for(std::size_t index=0;index<total;++index) {
            const Option& option=placement!=nullptr?*placement:pool[index];
            const CellVec& corridor=packer.corridor_pool[option.corridor];
            if(intersects(option.footprint,packer.occupied)||intersects(option.footprint,packer.access)
               ||intersects(corridor,packer.occupied)) continue;
            if(kind!="housing"&&(intersects(option.footprint,packer.reserved)
                                 ||intersects(corridor,packer.reserved))) continue;
            packer.occupied.insert(option.footprint.begin(),option.footprint.end());
            for(const Cell& c:corridor)
                if(!std::binary_search(option.footprint.begin(),option.footprint.end(),c))
                    packer.access.insert(c);
            for(const Cell& c:option.footprint) packer.reserved.erase(c);
            for(const Cell& c:corridor) packer.reserved.erase(c);
            if(kind=="housing") {
                for(std::size_t k=0;k<packer.housing_reserve.size();++k)
                    if(packer.option_equal(*packer.housing_reserve[k],option)) {
                        packer.housing_reserve.erase(packer.housing_reserve.begin()
                                                     +static_cast<std::ptrdiff_t>(k));
                        break;
                    }
            }
            Value& plots=*result.find("plots");
            Value plot=vobj();
            plot.set("id",vstr("plot-"+std::to_string(plots.items.size())));
            const Value* structure_id=find_field(row,"structure_id");
            const Value* row_id=find_field(row,"id");
            plot.set("building_id",structure_id!=nullptr?*structure_id
                     :(row_id!=nullptr?*row_id:Value::make_null()));
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
            plot.set("road_access",vpair(option.ax,option.az));
            plot.set("workers",vint(staffing_target_sum(row)));
            const Value* beds=find_field(row,"worker_beds");
            plot.set("beds",beds!=nullptr?*beds:vint(0));
            plots.items.push_back(std::move(plot));
            for(std::size_t p=0;p<7;++p) if(phase==phase_ids[p]) {++placed[p];break;}
            return true;
        }
        return false;
    };
    auto plot_sum=[&](const char* key) {
        std::int64_t total=0;
        for(const Value& plot:result.find("plots")->items) total+=field_int(plot,key);
        return total;
    };

    // Reserve gatehouse footprints on the enceinte openings before street-front packing.
    std::int64_t placed_gates=0,placed_towers=0;
    Value& fortification_value=*result.find("fortifications");
    if(fortifications.defended_perimeter&&gate_def.present&&gate_row!=nullptr
       &&find_field(*gate_row,"plot_m")!=nullptr) {
        Value& gate_values=*fortification_value.find("gates");
        for(std::size_t g=0;g<fortifications.gates.size();++g) {
            const FortificationGate& gate=fortifications.gates[g];
            const double x=gate.position_m.first,z=gate.position_m.second;
            // `gate.get('approach_m') or [x+1, z]`: an absent or empty approach falls
            // back to a point due east. The reference's gates always carry one.
            const double approach_x=gate.approach_m.first,approach_z=gate.approach_m.second;
            const double angle=std::atan2(approach_z-z,approach_x-x);
            const double degrees=round_to(py_degrees(angle),4);
            const Value& gate_plot=gate_row->at("plot_m");
            const double w=field_number(gate_plot,"width"),d=field_number(gate_plot,"depth");
            const CellVec footprint=to_vector(packer.cells(x,z,w,d,angle));
            double ground_min=0.,ground_max=0.;
            bool first=true;
            auto observe=[&](double value) {
                if(first) {ground_min=ground_max=value;first=false;return;}
                ground_min=std::min(ground_min,value);ground_max=std::max(ground_max,value);
            };
            for(const auto& corner:corners(x,z,w,d,angle))
                observe(sampler.sample(corner.first,corner.second,false).height);
            bool any_cell=false;
            for(const Cell& c:footprint) {
                auto found=heights.find(c);
                if(found!=heights.end()) {observe(found->second);any_cell=true;}
            }
            if(!any_cell) observe(sampler.sample(x,z,false).height);
            Option option;
            option.x=x;option.z=z;option.degrees=degrees;option.ax=x;option.az=z;
            option.footprint=footprint;
            option.corridor=packer.corridor_pool.size();
            packer.corridor_pool.push_back(footprint);
            option.ground_min=ground_min;option.ground_max=ground_max;
            if(install(*gate_row,"fortification","service",&option)) {
                ++placed_gates;
                gate_values.items[g].set("plot_id",result.find("plots")->items.back().at("id"));
            }
        }
    }
    if(fortifications.defended_perimeter&&tower_count_row!=nullptr) {
        Value& tower_values=*fortification_value.find("towers");
        const Value& tower_plot=tower_count_row->at("plot_m");
        const double w=field_number(tower_plot,"width"),d=field_number(tower_plot,"depth");
        for(std::size_t t=0;t<fortifications.towers.size();++t) {
            if(placed_towers>=tower_budget) break;
            const FortificationTower& tower=fortifications.towers[t];
            const double x=tower.position_m.first,z=tower.position_m.second;
            const CellVec footprint=to_vector(packer.cells(x,z,w,d,0));
            if(!subset(footprint,valid)||intersects(footprint,road)
               ||intersects(footprint,packer.occupied)) continue;
            double ground_min=0.,ground_max=0.;
            bool first=true;
            auto observe=[&](double value) {
                if(first) {ground_min=ground_max=value;first=false;return;}
                ground_min=std::min(ground_min,value);ground_max=std::max(ground_max,value);
            };
            for(const auto& corner:corners(x,z,w,d,0))
                observe(sampler.sample(corner.first,corner.second,false).height);
            for(const Cell& c:footprint) observe(heights.at(c));
            Option option;
            option.x=x;option.z=z;option.degrees=0.;option.ax=x;option.az=z;
            option.footprint=footprint;
            option.corridor=packer.corridor_pool.size();
            packer.corridor_pool.push_back(footprint);
            option.ground_min=ground_min;option.ground_max=ground_max;
            if(install(*tower_count_row,"fortification","service",&option)) {
                ++placed_towers;
                tower_values.items[t].set("plot_id",result.find("plots")->items.back().at("id"));
            }
        }
    }

    const double wooded_fraction=as_number(facts.at("wooded_fraction"));
    const Value* freshwater=find_field(site,"freshwater_distance_m");
    const Value* resource=find_field(site,"resource_potential");
    std::map<std::string,bool> conditions;
    conditions["usable_groundwater"]=false;
    conditions["water_collection_or_delivery"]=freshwater!=nullptr&&freshwater->kind!=Value::Kind::Null;
    conditions["navigable_shore"]=false;
    conditions["flowing_water"]=false;
    conditions["reliable_wind"]=false;
    conditions["ore_and_fuel_supply"]=(resource!=nullptr?as_number(*resource):0.)>=.5;
    conditions["food_surplus"]=false;
    conditions["working_animals"]=false;
    conditions["clay_and_fuel_supply"]=false;
    conditions["medicinal_supply"]=wooded_fraction>.1;
    conditions["clear_sky_view"]=true;
    conditions["isolation_access"]=true;
    conditions["defended_perimeter"]=fortifications.defended_perimeter;

    struct ProgramRow {const Value* row;std::int64_t count;};
    std::vector<ProgramRow> high,low;
    {
        Value& unplaced=*result.find("unplaced");
        const Value* buildings=find_field(preset,"buildings");
        if(buildings!=nullptr)
            for(const Value& row:buildings->items) {
                const std::string structure_id=row.at("structure_id").text;
                std::int64_t remaining=field_int(row,"count");
                if(structure_id=="building.gatehouse") remaining=std::max<std::int64_t>(0,remaining-placed_gates);
                if(structure_id=="building.tower") remaining=std::max<std::int64_t>(0,remaining-placed_towers);
                if(remaining<=0) continue;
                std::string missing;
                bool any_missing=false;
                for(const Value& condition:row.at("placement_conditions").items) {
                    auto found=conditions.find(condition.text);
                    if(found!=conditions.end()&&found->second) continue;
                    if(any_missing) missing+=", ";
                    missing+=condition.text;
                    any_missing=true;
                }
                if(any_missing) {
                    Value item=vobj();
                    item.set("building_id",vstr(structure_id));
                    item.set("count",vint(remaining));
                    item.set("reason",vstr("Unverified prerequisite: "+missing));
                    unplaced.items.push_back(std::move(item));
                    continue;
                }
                (row.at("priority").text=="core"?high:low).push_back(ProgramRow{&row,remaining});
            }
    }

    const std::int64_t house_beds=field_int(house,"worker_beds");
    const double house_w=field_number(house_plot,"width"),house_d=field_number(house_plot,"depth");
    // Hold street-front plots so later service packing cannot starve worker houses.
    auto reserve_housing=[&](std::int64_t worker_budget) {
        const std::int64_t deficit=std::max<std::int64_t>(0,worker_budget-plot_sum("beds"));
        const auto wanted=static_cast<std::int64_t>(std::ceil(
            static_cast<double>(deficit)/static_cast<double>(house_beds)));
        std::int64_t need=std::max<std::int64_t>(0,wanted
            -static_cast<std::int64_t>(packer.housing_reserve.size()));
        for(const Option& option:packer.candidates(house_w,house_d)) {
            if(need<=0) break;
            const CellVec& corridor=packer.corridor_pool[option.corridor];
            if(intersects(option.footprint,packer.occupied)||intersects(option.footprint,packer.access)
               ||intersects(corridor,packer.occupied)) continue;
            if(intersects(option.footprint,packer.reserved)||intersects(corridor,packer.reserved)) continue;
            packer.reserved.insert(option.footprint.begin(),option.footprint.end());
            packer.reserved.insert(corridor.begin(),corridor.end());
            packer.housing_reserve.push_back(&option);
            --need;
        }
    };
    auto release=[&](const Option& option) {
        for(const Cell& c:option.footprint) packer.reserved.erase(c);
        for(const Cell& c:packer.corridor_pool[option.corridor]) packer.reserved.erase(c);
    };
    auto house_workers=[&](const std::string& phase) {
        std::int64_t workers=plot_sum("workers"),beds=plot_sum("beds");
        Value audit=vobj();
        audit.set("phase",vstr(phase));
        audit.set("workers",vint(workers));
        audit.set("starting_beds",vint(beds));
        audit.set("houses_placed",vint(0));
        audit.set("upgrades",vint(0));
        audit.set("plots_exhausted",vbool(false));
        audit.set("reserved_slots",vint(static_cast<std::int64_t>(packer.housing_reserve.size())));
        std::int64_t houses_placed=0,upgrades=0;
        bool exhausted=false;
        while(beds<workers) {
            const Option* placement=packer.housing_reserve.empty()?nullptr:packer.housing_reserve.front();
            if(!install(house,phase,"housing",placement)) {
                if(placement!=nullptr) {
                    // Reserved slot became unusable; drop it and keep seeking frontage.
                    packer.housing_reserve.erase(packer.housing_reserve.begin());
                    release(*placement);
                    continue;
                }
                exhausted=true;break;
            }
            ++houses_placed;
            beds+=house_beds;
        }
        // Replace existing dwellings in place: access and occupied land stay valid.
        const std::string house_id=house.at("id").text;
        const std::int64_t apartment_beds=field_int(apartment,"worker_beds");
        for(Value& plot:result.find("plots")->items) {
            if(beds>=workers) break;
            const Value* building_id=find_field(plot,"building_id");
            if(building_id==nullptr||!building_id->is_string()||building_id->text!=house_id) continue;
            ++upgrades;
            if(find_field(plot,"housing_upgrade")==nullptr) {
                Value previous=vobj();
                for(const char* key:{"building_id","name","dimensions_m","beds"})
                    previous.set(key,plot.at(key));
                Value upgrade=vobj();
                upgrade.set("phase",vstr(phase));
                upgrade.set("previous",std::move(previous));
                plot.set("housing_upgrade",std::move(upgrade));
            }
            beds+=apartment_beds-field_int(plot,"beds");
            plot.set("building_id",apartment.at("id"));
            plot.set("name",apartment.at("name"));
            plot.set("dimensions_m",apartment.at("dimensions_m"));
            plot.set("beds",apartment.at("worker_beds"));
        }
        // Unused housing holds are released so later services may use the land.
        while(!packer.housing_reserve.empty()) {
            const Option* option=packer.housing_reserve.back();
            packer.housing_reserve.pop_back();
            release(*option);
        }
        audit.set("houses_placed",vint(houses_placed));
        audit.set("upgrades",vint(upgrades));
        audit.set("plots_exhausted",vbool(exhausted));
        audit.set("final_beds",vint(beds));
        audit.set("shortfall",vint(std::max<std::int64_t>(0,workers-beds)));
        result.find("debug")->find("housing_passes")->items.push_back(std::move(audit));
    };

    for(int pass=0;pass<2;++pass) {
        const std::string priority=pass==0?"high":"low";
        const std::vector<ProgramRow>& rows=pass==0?high:low;
        if(priority=="low") {
            std::int64_t shortfall=0;
            for(const Value& plot:result.find("plots")->items)
                shortfall+=field_int(plot,"workers")-field_int(plot,"beds");
            if(shortfall>0) {
                Value& unplaced=*result.find("unplaced");
                for(const ProgramRow& entry:rows) {
                    Value item=vobj();
                    item.set("building_id",entry.row->at("structure_id"));
                    item.set("count",vint(entry.count));
                    item.set("reason",vstr("High-priority worker housing must be completed first"));
                    unplaced.items.push_back(std::move(item));
                }
                break;
            }
        }
        std::int64_t demand=plot_sum("workers");
        for(const ProgramRow& entry:rows) demand+=staffing_target_sum(*entry.row)*entry.count;
        reserve_housing(demand);
        Value* debug_value=result.find("debug");
        if(debug_value->find("housing_reservations")==nullptr)
            debug_value->set("housing_reservations",varr());
        Value reservation=vobj();
        reservation.set("phase",vstr(priority));
        reservation.set("workers_budgeted",vint(demand));
        reservation.set("slots",vint(static_cast<std::int64_t>(packer.housing_reserve.size())));
        debug_value->find("housing_reservations")->items.push_back(std::move(reservation));
        for(const ProgramRow& entry:rows) {
            std::int64_t failed=0;
            for(std::int64_t k=0;k<entry.count;++k)
                if(!install(*entry.row,priority,"service",nullptr)) ++failed;
            if(failed!=0) {
                Value item=vobj();
                item.set("building_id",entry.row->at("structure_id"));
                item.set("count",vint(failed));
                item.set("reason",vstr("No terrain-safe plot with road access remaining"));
                result.find("unplaced")->items.push_back(std::move(item));
            }
        }
        house_workers(priority+"_housing");
    }

    const std::int64_t workers=plot_sum("workers"),beds=plot_sum("beds");
    {
        Value* debug_value=result.find("debug");
        debug_value->set("shape_safe_cells",vint(static_cast<std::int64_t>(valid.size())));
        debug_value->set("road_cells",vint(static_cast<std::int64_t>(road.size())));
        debug_value->set("occupied_cells",vint(static_cast<std::int64_t>(packer.occupied.size())));
        debug_value->set("access_cells",vint(static_cast<std::int64_t>(packer.access.size())));
        std::int64_t vacant=0;
        for(const Cell& c:valid)
            if(road.count(c)==0&&packer.occupied.count(c)==0&&packer.access.count(c)==0) ++vacant;
        debug_value->set("vacant_shape_cells",vint(vacant));
        debug_value->set("housing_frontage_candidates",vint(packer.free_frontage(house_w,house_d)));
        debug_value->set("fortification_rings",vint(static_cast<std::int64_t>(fortifications.rings.size())));
        debug_value->set("program_half_m",vint(half));
    }
    std::set<std::string> core_ids;
    {
        const Value* buildings=find_field(preset,"buildings");
        if(buildings!=nullptr)
            for(const Value& row:buildings->items)
                if(row.at("priority").text=="core") core_ids.insert(row.at("structure_id").text);
    }
    std::int64_t failed_core=0,unplaced_total=0;
    for(const Value& row:result.find("unplaced")->items) {
        const std::int64_t count=field_int(row,"count");
        unplaced_total+=count;
        const Value& building_id=row.at("building_id");
        if(building_id.is_string()&&core_ids.count(building_id.text)!=0) failed_core+=count;
    }
    result.set("status",vstr(failed_core==0&&beds>=workers?"complete":"partial"));
    {
        std::int64_t service=0,houses=0,apartments=0;
        PySum plot_area;
        const std::string house_id=house.at("id").text;
        const std::string apartment_id=apartment.at("id").text;
        for(const Value& plot:result.find("plots")->items) {
            if(plot.at("kind").text=="service") ++service;
            const Value& building_id=plot.at("building_id");
            if(building_id.is_string()&&building_id.text==house_id) ++houses;
            if(building_id.is_string()&&building_id.text==apartment_id) ++apartments;
            const Value& plot_m=plot.at("plot_m");
            plot_area.add_product(plot_m.at("width"),plot_m.at("depth"));
        }
        const Value* urban=find_field(site,"urban_population_estimate");
        const Value* population=find_field(site,"population_estimate");
        Value stats=vobj();
        stats.set("workers",vint(workers));
        stats.set("worker_beds",vint(beds));
        stats.set("housing_shortfall",vint(std::max<std::int64_t>(0,workers-beds)));
        stats.set("service_buildings",vint(service));
        stats.set("houses",vint(houses));
        stats.set("apartments",vint(apartments));
        stats.set("unplaced_core",vint(failed_core));
        stats.set("unplaced_total",vint(unplaced_total));
        stats.set("simulation_population",urban!=nullptr?*urban
                  :(population!=nullptr?*population:Value::make_null()));
        stats.set("reserved_plot_area_m2",plot_area.value());
        stats.set("wall_segments",vint(static_cast<std::int64_t>(fortifications.segments.size())));
        stats.set("defended_perimeter",vbool(fortifications.defended_perimeter));
        result.set("stats",std::move(stats));
    }
    {
        Value& pass_values=*result.find("passes");
        for(std::size_t p=0;p<pass_values.items.size();++p)
            pass_values.items[p].set("placed",vint(placed[p]));
    }
    return result;
}

Value fill_cities(const World& world) {
    std::vector<std::size_t> order(world.sites.size());
    for(std::size_t i=0;i<order.size();++i) order[i]=i;
    // sorted(..., key=lambda s: str(s.get('uid', s['id']))): Python's sort is stable,
    // and two sites may share a key, so the original order has to survive a tie.
    std::stable_sort(order.begin(),order.end(),[&](std::size_t a,std::size_t b) {
        return py_str(site_uid_or_id(world.sites[a]))<py_str(site_uid_or_id(world.sites[b]));
    });
    Value cities=varr();
    std::map<std::string,std::int64_t> counts;
    for(std::size_t index:order) {
        Value plan=plan_city(world,world.sites[index],counts);
        const Value& shape=plan.at("shape");
        const Value& shape_id=shape.at("shape_id");
        cities.items.push_back(std::move(plan));
        if(shape_id.is_string()&&!shape_id.text.empty()) ++counts[shape_id.text];
    }
    Value out=vobj();
    out.set("version",vint(planner_version));
    out.set("identity",planner_identity());
    out.set("cities",std::move(cities));
    Value order_value=varr();
    for(const char* key:{"map","shape","fortification","high","high_housing","low","low_housing"})
        order_value.items.push_back(vstr(key));
    out.set("phase_order",std::move(order_value));
    out.set("scope",vstr("Schematic local metres from final world raster; does not change simulated population."));
    return out;
}
}
