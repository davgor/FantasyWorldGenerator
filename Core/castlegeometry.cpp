#include "castlegeometry.hpp"
#include "globe.hpp"
#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
namespace fantasy_world_generator {
namespace {
using Pair=std::pair<double,double>;
// math.degrees multiplies by this one constant; it is not a division per call.
constexpr double rad_to_deg=180./pi;
// math.dist over two dimensions and math.hypot run through the same CPython
// vector_norm, so the ported hypot answers both.
double py_dist(const Pair& a,const Pair& b) {
    return python_hypot(a.first-b.first,a.second-b.second);
}
// Python's % follows the divisor's sign and its // floors; C++ truncates toward zero.
std::int64_t py_mod(std::int64_t value,std::int64_t modulus) {
    const std::int64_t remainder=value%modulus;
    return remainder!=0 && ((remainder<0)!=(modulus<0)) ? remainder+modulus : remainder;
}
std::int64_t py_floordiv(std::int64_t value,std::int64_t divisor) {
    const std::int64_t quotient=value/divisor;
    const std::int64_t remainder=value%divisor;
    return remainder!=0 && ((remainder<0)!=(divisor<0)) ? quotient-1 : quotient;
}
// Decimal digits, most significant first, with no leading zeros; empty is zero.
using Digits=std::vector<std::uint8_t>;
void strip(Digits& digits) {
    std::size_t lead=0;
    while(lead<digits.size() && digits[lead]==0) ++lead;
    digits.erase(digits.begin(),digits.begin()+static_cast<std::ptrdiff_t>(lead));
}
// Halve in place, returning the bit that fell off the bottom.
bool halve(Digits& digits) {
    int carry=0;
    for(std::uint8_t& digit:digits) {
        const int current=carry*10+digit;
        digit=static_cast<std::uint8_t>(current/2);
        carry=current%2;
    }
    strip(digits);
    return carry!=0;
}
void twice(Digits& digits) {
    int carry=0;
    for(std::size_t i=digits.size();i-->0;) {
        const int current=digits[i]*2+carry;
        digits[i]=static_cast<std::uint8_t>(current%10);
        carry=current/10;
    }
    if(carry) digits.insert(digits.begin(),static_cast<std::uint8_t>(carry));
}
void increment(Digits& digits) {
    for(std::size_t i=digits.size();i-->0;) {
        if(digits[i]<9) {++digits[i];return;}
        digits[i]=0;
    }
    digits.insert(digits.begin(),1);
}
// |value| * 10^places rounded to an integer, ties to even, on the exact binary value.
// This is what CPython's _Py_dg_dtoa in mode 3 computes, and both round(x, n) and
// format(x, '.nf') are built on it. It is derived here rather than taken from snprintf
// because the C library's tie behaviour at the rounded digit is not specified to match,
// and a coordinate landing exactly on a half is not rare: every ellipse sample is a
// product of two short binary fractions.
Digits scaled_round(double value,int places) {
    Digits digits;
    if(value==0.) return digits;
    int exponent=0;
    const double fraction=std::frexp(std::fabs(value),&exponent);
    const auto mantissa=static_cast<std::uint64_t>(std::ldexp(fraction,53));
    const int shift=exponent-53;
    char buffer[24];
    std::snprintf(buffer,sizeof buffer,"%llu",static_cast<unsigned long long>(mantissa));
    for(const char* cursor=buffer;*cursor;++cursor)
        digits.push_back(static_cast<std::uint8_t>(*cursor-'0'));
    for(int i=0;i<places;++i) digits.push_back(0);
    strip(digits);
    // A value at or above 2^53 is already a whole number of these units: nothing to
    // round, and the doublings stay exact.
    if(shift>0) {
        for(int i=0;i<shift;++i) twice(digits);
        return digits;
    }
    // The bits leaving the bottom decide the rounding: the last one out is the half,
    // everything before it is the sticky remainder.
    bool sticky=false,half=false;
    for(int i=0;i<-shift;++i) {
        sticky=sticky||half;
        half=digits.empty()?false:halve(digits);
        if(digits.empty() && !half) break;
    }
    if(half && (sticky || (!digits.empty() && digits.back()%2==1))) increment(digits);
    return digits;
}
// format(value, '.<places>f').
std::string format_fixed(double value,int places) {
    if(std::isnan(value)) return "nan";
    if(std::isinf(value)) return value<0.?"-inf":"inf";
    const Digits digits=scaled_round(value,places);
    std::string body;
    for(std::uint8_t digit:digits) body.push_back(static_cast<char>('0'+digit));
    while(static_cast<int>(body.size())<places+1) body.insert(body.begin(),'0');
    const std::size_t split=body.size()-static_cast<std::size_t>(places);
    std::string text=std::signbit(value)?"-":"";
    text+=body.substr(0,split);
    if(places>0) {text+=".";text+=body.substr(split);}
    return text;
}
// repr(value) for a float: the shortest digits that read back as the same double, laid
// out the way CPython lays them out. The digits come from to_chars, which is specified
// to produce that same shortest round trip; the layout rule -- scientific only when the
// decimal point falls at or below -4 or above 16, and a fixed result always carrying a
// fractional part -- is CPython's, and differs from what %g or to_chars would choose.
std::string python_repr(double value) {
    if(std::isnan(value)) return "nan";
    if(std::isinf(value)) return value<0.?"-inf":"inf";
    char buffer[64];
    const std::to_chars_result written=std::to_chars(buffer,buffer+sizeof buffer,value,
                                                     std::chars_format::scientific);
    const std::string form(buffer,written.ptr);
    const std::size_t marker=form.find('e');
    std::string mantissa=form.substr(0,marker);
    const int exponent=std::atoi(form.c_str()+marker+1);
    std::string sign;
    if(!mantissa.empty() && mantissa[0]=='-') {sign="-";mantissa.erase(mantissa.begin());}
    std::string digits;
    for(char character:mantissa) if(character!='.') digits.push_back(character);
    const int count=static_cast<int>(digits.size());
    const int point=exponent+1;
    std::string text=sign;
    if(point<=-4 || point>16) {
        text+=digits.substr(0,1);
        if(count>1) {text+=".";text+=digits.substr(1);}
        const int power=point-1;
        char tail[16];
        std::snprintf(tail,sizeof tail,"e%c%02d",power<0?'-':'+',power<0?-power:power);
        text+=tail;
    } else if(point<=0) {
        text+="0.";
        text.append(static_cast<std::size_t>(-point),'0');
        text+=digits;
    } else if(point>=count) {
        text+=digits;
        text.append(static_cast<std::size_t>(point-count),'0');
        text+=".0";
    } else {
        text+=digits.substr(0,static_cast<std::size_t>(point));
        text+=".";
        text+=digits.substr(static_cast<std::size_t>(point));
    }
    return text;
}
// Signed heading change of the polyline a->b->c. This is city_fortifications'
// path_turn_degrees, which differs from turn_degrees below: it subtracts the incoming
// heading rather than measuring both legs out of b, and the two disagree by 180
// degrees. Duplicated here on purpose so this module does not depend on a file another
// port owns; the two copies should become one once both have landed.
double path_turn_degrees(const Pair& a,const Pair& b,const Pair& c) {
    double delta=(std::atan2(c.second-b.second,c.first-b.first)
                  -std::atan2(b.second-a.second,b.first-a.first))*rad_to_deg;
    while(delta<=-180.) delta+=360.;
    while(delta>180.) delta-=360.;
    return delta;
}
// city_fortifications' smooth_closed_ring, duplicated for the same reason. The centre
// is a builtin sum() over floats, so it is Neumaier compensated, not a running add.
// Fewer than eight points come back untouched and unrounded.
std::vector<Pair> smooth_closed_ring(const std::vector<Pair>& points) {
    constexpr double max_turn_degrees=95.,radius_factor=1.12;
    constexpr int passes=12;
    if(points.size()<8) return points;
    std::vector<Pair> pts=points;
    const std::size_t n=pts.size();
    Sum centre_x,centre_z;
    for(const Pair& point:pts) {centre_x.add(point.first);centre_z.add(point.second);}
    const double cx=centre_x.value()/static_cast<double>(n);
    const double cz=centre_z.value()/static_cast<double>(n);
    for(int pass=0;pass<passes;++pass) {
        std::vector<double> radii(n);
        for(std::size_t i=0;i<n;++i) {
            const double radius=python_hypot(pts[i].first-cx,pts[i].second-cz);
            radii[i]=radius!=0.?radius:1.;
        }
        std::vector<Pair> pulled(n);
        for(std::size_t i=0;i<n;++i) {
            const double before=radii[(i+n-1)%n],after=radii[(i+1)%n];
            // Python's max returns the second only when it is strictly greater, and
            // min the second only when it is strictly less.
            const double cap=radius_factor*(after>before?after:before);
            const double radius=cap<radii[i]?cap:radii[i];
            const double ux=(pts[i].first-cx)/radii[i],uz=(pts[i].second-cz)/radii[i];
            pulled[i]={cx+ux*radius,cz+uz*radius};
        }
        pts=pulled;
        std::vector<Pair> relaxed(n);
        for(std::size_t i=0;i<n;++i) {
            const Pair& before=pts[(i+n-1)%n];
            const Pair& after=pts[(i+1)%n];
            if(std::fabs(path_turn_degrees(before,pts[i],after))>max_turn_degrees)
                relaxed[i]={(before.first+2*pts[i].first+after.first)/4,
                            (before.second+2*pts[i].second+after.second)/4};
            else relaxed[i]=pts[i];
        }
        pts=relaxed;
    }
    std::vector<Pair> result(n);
    for(std::size_t i=0;i<n;++i)
        result[i]={python_round(pts[i].first,2),python_round(pts[i].second,2)};
    return result;
}
bool carries_end(const std::vector<std::string>& ends,const std::string& end) {
    for(const std::string& candidate:ends) if(candidate==end) return true;
    return false;
}
}
double python_round(double value,int ndigits) {
    if(!std::isfinite(value)) return value;
    if(value==0.) return value;
    int exponent=0;
    std::frexp(std::fabs(value),&exponent);
    // Already a whole number, so no decimal place can move: the reference reads its own
    // digits straight back.
    if(exponent-53>=0) return value;
    const Digits digits=scaled_round(value,ndigits);
    std::string text;
    if(digits.empty()) text="0";
    else for(std::uint8_t digit:digits) text.push_back(static_cast<char>('0'+digit));
    text+="e-";
    text+=std::to_string(ndigits);
    // strtod is correctly rounded, which is the _Py_dg_strtod the interpreter reads the
    // rounded decimal back with.
    return std::copysign(std::strtod(text.c_str(),nullptr),value);
}
double turn_degrees(const Pair& a,const Pair& b,const Pair& c) {
    const double first_x=a.first-b.first,first_z=a.second-b.second;
    const double second_x=c.first-b.first,second_z=c.second-b.second;
    const double incoming=std::atan2(first_z,first_x);
    const double outgoing=std::atan2(second_z,second_x);
    double delta=(outgoing-incoming)*rad_to_deg;
    while(delta<=-180.) delta+=360.;
    while(delta>180.) delta-=360.;
    return delta;
}
CastleJoinResult can_join(const CastleModule* module_a,const CastleModule* module_b,
                          const CastleJoinRules& rules,const CastleMeasure& thickness_a,
                          const CastleMeasure& thickness_b,const CastleMeasure& height_a,
                          const CastleMeasure& height_b) {
    if(module_a==nullptr || module_b==nullptr) return {false,true,"Missing module"};
    if(!module_a->has_end_type || !module_b->has_end_type)
        return {false,true,"Module has no join end"};
    if(!carries_end(module_a->compatible_ends,module_b->end_type)
       && !carries_end(module_b->compatible_ends,module_a->end_type))
        return {false,true,"Incompatible ends "+module_a->end_type+"/"+module_b->end_type};
    const CastleMeasure ta=thickness_a.set?thickness_a
        :CastleMeasure{module_a->has_thickness,module_a->thickness_nominal};
    const CastleMeasure tb=thickness_b.set?thickness_b
        :CastleMeasure{module_b->has_thickness,module_b->thickness_nominal};
    const CastleMeasure ha=height_a.set?height_a
        :CastleMeasure{module_a->has_height,module_a->height_nominal};
    const CastleMeasure hb=height_b.set?height_b
        :CastleMeasure{module_b->has_height,module_b->height_nominal};
    if(!ta.set || !tb.set || !ha.set || !hb.set)
        return {false,true,"Missing thickness or height"};
    if(std::fabs(ta.value-tb.value)>rules.max_thickness_delta_m)
        return {false,true,"Thickness delta "+format_fixed(std::fabs(ta.value-tb.value),3)
                           +" exceeds "+python_repr(rules.max_thickness_delta_m)};
    if(std::fabs(ha.value-hb.value)>rules.max_height_delta_m)
        return {false,true,"Height delta "+format_fixed(std::fabs(ha.value-hb.value),3)
                           +" exceeds "+python_repr(rules.max_height_delta_m)};
    // A walkway key the module simply does not carry is not the same as one set False:
    // only an explicit False breaks continuity.
    const bool walkway_a=module_a->has_walkway && module_a->walkway;
    const bool walkway_b=module_b->has_walkway && module_b->walkway;
    const bool denied_a=module_a->has_walkway && !module_a->walkway;
    const bool denied_b=module_b->has_walkway && !module_b->walkway;
    if(rules.walkway_required && walkway_a && denied_b)
        return {false,true,"Walkway continuity broken"};
    if(rules.walkway_required && walkway_b && denied_a)
        return {false,true,"Walkway continuity broken"};
    return {true,false,std::string()};
}
std::vector<Pair> ellipse_ring(double rx,double rz,std::int64_t samples) {
    std::vector<Pair> points;
    if(samples>0) points.reserve(static_cast<std::size_t>(samples));
    for(std::int64_t i=0;i<samples;++i) {
        // (2 * pi) * i, then divided: the reference's left-to-right order, and 2 * pi
        // is exact, so the only rounding is the multiply and the divide.
        const double angle=2*pi*static_cast<double>(i)/static_cast<double>(samples);
        points.emplace_back(python_round(rx*std::cos(angle),2),python_round(rz*std::sin(angle),2));
    }
    return points;
}
std::vector<Pair> clip_ring_to_valid(const std::vector<Pair>& points,const std::set<Cell>& valid,
                                     double half,std::int64_t cell,double max_slope_deg,
                                     const std::map<Cell,double>& slope) {
    if(points.empty() || valid.empty()) return {};
    // int(max(half, 1)) truncates toward zero, and max keeps the integer 1 only when it
    // is strictly greater.
    const std::int64_t start=1.>half?1:static_cast<std::int64_t>(half);
    std::vector<Pair> snapped;
    for(const Pair& point:points) {
        const double measured=python_hypot(point.first,point.second);
        const double length=measured!=0.?measured:1.;
        const double ux=point.first/length,uz=point.second/length;
        bool found=false;
        Pair best{0.,0.};
        for(std::int64_t dist=start;cell>0 && dist>0;dist-=cell) {
            const double x=ux*static_cast<double>(dist),z=uz*static_cast<double>(dist);
            // math.floor first: a cast would truncate toward zero and shift the whole
            // ring by a cell on the negative side of the raster.
            const auto i=static_cast<std::int64_t>(std::floor((x+half)/static_cast<double>(cell)));
            const auto j=static_cast<std::int64_t>(std::floor((z+half)/static_cast<double>(cell)));
            const Cell candidate(i,j);
            if(valid.count(candidate)==0) continue;
            if(slope.at(candidate)>max_slope_deg) continue;
            best={python_round(x,2),python_round(z,2)};
            found=true;
            break;
        }
        if(found) snapped.push_back(best);
    }
    return snapped.size()>=8?smooth_closed_ring(snapped):snapped;
}
void segmentize(const std::vector<Pair>& polyline,double segment_depth_m,
                const std::string& structure_id,const std::string& ring_id,double thickness_m,
                double height_m,std::vector<CastleSegment>& segments,
                std::vector<CastleRingNode>& nodes) {
    segments.clear();
    nodes.clear();
    if(polyline.size()<3) return;
    for(std::size_t i=0;i<polyline.size();++i) {
        CastleRingNode node;
        node.id=ring_id+"-node-"+std::to_string(i);
        node.kind="vertex";
        node.ring_id=ring_id;
        node.position_m=polyline[i];
        nodes.push_back(node);
    }
    std::vector<Pair> closed=polyline;
    closed.push_back(polyline[0]);
    std::int64_t seg_i=0;
    double carry=0.;
    std::vector<Pair> path;
    for(std::size_t index=0;index+1<closed.size();++index) {
        Pair a=closed[index];
        const Pair b=closed[index+1];
        path.push_back(a);
        double edge=py_dist(a,b);
        while(carry+edge>=segment_depth_m-0.01) {
            const double need=segment_depth_m-carry;
            // `need / edge if edge else 0`: only a zero edge takes the other branch.
            const double t=edge!=0.?need/edge:0.;
            const Pair end{python_round(a.first+(b.first-a.first)*t,2),
                           python_round(a.second+(b.second-a.second)*t,2)};
            const Pair start=path.empty()?a:path.back();
            const Pair mid{(start.first+end.first)/2,(start.second+end.second)/2};
            const double heading=std::atan2(end.second-start.second,end.first-start.first)*rad_to_deg;
            const double angle=heading-90;
            CastleSegment segment;
            segment.id=ring_id+"-seg-"+std::to_string(seg_i);
            segment.ring_id=ring_id;
            segment.structure_id=structure_id;
            segment.module_id="module.curtain_segment";
            segment.from_m=start;
            segment.to_m=end;
            segment.center_m={python_round(mid.first,2),python_round(mid.second,2)};
            segment.length_m=python_round(py_dist(start,end),3);
            segment.rotation_degrees=python_round(angle,4);
            segment.thickness_m=thickness_m;
            segment.height_m=height_m;
            segment.walkway=true;
            segments.push_back(segment);
            ++seg_i;
            path.assign(1,end);
            // The reference rebinds the leg's start to the cut, so the next pass
            // measures what is left of this edge, not the whole of it.
            a=end;
            edge=py_dist(a,b);
            carry=0.;
        }
        carry+=edge;
    }
}
std::vector<std::int64_t> corner_indices(const std::vector<Pair>& polyline,double min_turn_degrees) {
    std::vector<std::int64_t> hits;
    if(polyline.size()<3) return hits;
    const auto n=static_cast<std::int64_t>(polyline.size());
    for(std::int64_t i=0;i<n;++i) {
        const Pair& a=polyline[static_cast<std::size_t>(py_mod(i-1,n))];
        const Pair& b=polyline[static_cast<std::size_t>(i)];
        const Pair& c=polyline[static_cast<std::size_t>(py_mod(i+1,n))];
        if(std::fabs(turn_degrees(a,b,c))>=min_turn_degrees) hits.push_back(i);
    }
    return hits;
}
std::int64_t approach_gate_index(const std::vector<Pair>& polyline,const CastleApproach& approach_m) {
    if(polyline.empty()) return -1;
    const auto n=static_cast<std::int64_t>(polyline.size());
    std::int64_t best=0;
    if(!approach_m.set) {
        // max over the key (x, -abs(z)): a plain tuple comparison, and max replaces the
        // incumbent only on a strict increase.
        double best_x=polyline[0].first,best_z=-std::fabs(polyline[0].second);
        for(std::int64_t i=1;i<n;++i) {
            const double x=polyline[static_cast<std::size_t>(i)].first;
            const double z=-std::fabs(polyline[static_cast<std::size_t>(i)].second);
            if(x>best_x || (x==best_x && z>best_z)) {best=i;best_x=x;best_z=z;}
        }
        return best;
    }
    double best_distance=py_dist(polyline[0],approach_m.value);
    for(std::int64_t i=1;i<n;++i) {
        const double distance=py_dist(polyline[static_cast<std::size_t>(i)],approach_m.value);
        if(distance<best_distance) {best=i;best_distance=distance;}
    }
    return best;
}
std::int64_t opposite_index(const std::vector<Pair>& polyline,std::int64_t index) {
    if(polyline.empty()) return -1;
    const auto n=static_cast<std::int64_t>(polyline.size());
    return py_mod(index+py_floordiv(n,2),n);
}
std::vector<CastleJoinFailure> validate_segment_chain(
    const std::vector<CastleSegment>& segments,const std::vector<CastleJoinNode>& nodes_by_join,
    const std::map<std::string,CastleModule>& modules,const CastleJoinRules& rules) {
    std::vector<CastleJoinFailure> failures;
    const CastleModule& curtain=modules.at("curtain_segment");
    for(const CastleSegment& segment:segments) {
        const CastleJoinResult result=can_join(&curtain,&curtain,rules,{true,segment.thickness_m},
                                               {true,segment.thickness_m},{true,segment.height_m},
                                               {true,segment.height_m});
        if(!result.ok) {
            CastleJoinFailure failure;
            failure.is_segment=true;
            failure.has_id=true;
            failure.id=segment.id;
            failure.reason=result.reason;
            failures.push_back(failure);
        }
    }
    for(const CastleJoinNode& join:nodes_by_join) {
        const auto found=modules.find(join.module_key);
        const CastleModule* module=found==modules.end()?nullptr:&found->second;
        // A node may rise above the walkway, so join continuity is checked at the
        // curtain's height on both sides.
        const double join_h=join.has_curtain_height?join.curtain_height_m:curtain.height_nominal;
        const CastleJoinResult result=can_join(&curtain,module,rules,
                                               {join.has_thickness,join.thickness_m},
                                               {join.has_thickness,join.thickness_m},
                                               {true,join_h},{true,join_h});
        if(!result.ok) {
            CastleJoinFailure failure;
            failure.is_segment=false;
            failure.has_id=!join.id.empty();
            failure.id=join.id;
            failure.reason=result.reason.empty()?std::string("join failed"):result.reason;
            failures.push_back(failure);
        }
    }
    return failures;
}
CastleWallNetwork build_wall_network(const std::string& ring_id,const std::string& role,
                                     const std::vector<Pair>& polyline,
                                     const CastleApproach& approach_m,
                                     const CastleRingSpec& ring_spec,
                                     const std::map<std::string,CastleModule>& modules,
                                     const CastleJoinRules& rules,bool ditch) {
    CastleWallNetwork report;
    report.id=ring_id;
    report.role=role;
    report.polyline_m=polyline;
    report.status="open";
    report.walkway_continuous=false;
    if(polyline.size()<8) {
        report.unplaced.push_back({true,"building.curtain_segment","Perimeter could not close"});
        return report;
    }
    const CastleModule& curtain=modules.at("curtain_segment");
    const double thickness=curtain.thickness_nominal;
    const double height=curtain.height_nominal;
    std::vector<CastleSegment> segments;
    std::vector<CastleRingNode> vertices;
    segmentize(polyline,rules.segment_depth_m,curtain.structure_id,ring_id,thickness,height,
               segments,vertices);
    if(segments.size()<6) {
        report.unplaced.push_back({true,curtain.structure_id,
                                   "Insufficient continuous wall segments"});
        return report;
    }
    const std::int64_t gate_idx=approach_gate_index(polyline,approach_m);
    const std::string gate_key=ring_spec.gate.empty()?std::string("gatehouse"):ring_spec.gate;
    const CastleModule& gate_mod=modules.at(gate_key);
    std::vector<CastleJoinNode> gates;
    {
        CastleJoinNode gate;
        gate.id=ring_id+"-gate-0";
        gate.ring_id=ring_id;
        gate.module_key=gate_key;
        gate.module_id=gate_mod.id;
        gate.structure_id=gate_mod.structure_id;
        gate.position_m=polyline[static_cast<std::size_t>(gate_idx)];
        gate.has_approach=true;
        gate.approach_m=approach_m.set?approach_m.value:polyline[static_cast<std::size_t>(gate_idx)];
        gate.has_thickness=true;
        gate.thickness_m=thickness;
        gate.height_m=gate_mod.height_nominal;
        gate.has_curtain_height=true;
        gate.curtain_height_m=height;
        gate.walkway=true;
        gates.push_back(gate);
    }
    if(ring_spec.postern) {
        const std::int64_t post_idx=opposite_index(polyline,gate_idx);
        const CastleModule& post_mod=modules.at("postern");
        CastleJoinNode postern;
        postern.id=ring_id+"-postern-0";
        postern.ring_id=ring_id;
        postern.module_key="postern";
        postern.module_id=post_mod.id;
        postern.structure_id=post_mod.structure_id;
        postern.position_m=polyline[static_cast<std::size_t>(post_idx)];
        postern.has_approach=true;
        postern.approach_m=polyline[static_cast<std::size_t>(post_idx)];
        postern.has_thickness=true;
        postern.thickness_m=thickness;
        postern.height_m=post_mod.height_nominal;
        postern.has_curtain_height=true;
        postern.curtain_height_m=height;
        postern.walkway=true;
        postern.kind="postern";
        gates.push_back(postern);
    }
    // Drop curtain segments that collide with gate centres. max(8, depth * 0.6) keeps
    // the integer 8 unless the scaled depth is strictly greater.
    const double clearance=rules.segment_depth_m*.6;
    const double limit=clearance>8.?clearance:8.;
    std::vector<CastleSegment> keep;
    for(const CastleSegment& segment:segments) {
        bool blocked=false;
        for(const CastleJoinNode& gate:gates)
            if(py_dist(segment.center_m,gate.position_m)<limit) {blocked=true;break;}
        if(!blocked) keep.push_back(segment);
    }
    std::vector<CastleJoinNode> towers;
    const std::vector<std::int64_t> hits=corner_indices(polyline,rules.min_turn_degrees_for_corner);
    for(std::size_t t_i=0;t_i<hits.size();++t_i) {
        // The budget counts corners considered, not towers placed: a corner skipped for
        // sitting on a gate still spends its slot.
        if(static_cast<std::int64_t>(t_i)>=ring_spec.tower_budget) break;
        const auto idx=static_cast<std::size_t>(hits[t_i]);
        bool blocked=false;
        for(const CastleJoinNode& gate:gates)
            if(py_dist(polyline[idx],gate.position_m)<10.) {blocked=true;break;}
        if(blocked) continue;
        const CastleModule& corner=modules.at("corner_join");
        CastleJoinNode tower;
        tower.id=ring_id+"-tower-"+std::to_string(t_i);
        tower.ring_id=ring_id;
        tower.module_key="corner_join";
        tower.module_id=corner.id;
        tower.structure_id=corner.structure_id;
        tower.position_m=polyline[idx];
        tower.has_thickness=true;
        tower.thickness_m=thickness;
        tower.height_m=corner.height_nominal;
        tower.has_curtain_height=true;
        tower.curtain_height_m=height;
        tower.walkway=true;
        towers.push_back(tower);
    }
    std::vector<CastleJoinNode> stairs;
    const std::int64_t stair_budget=ring_spec.stairs;
    if(stair_budget!=0 && !keep.empty()) {
        const std::int64_t divided=py_floordiv(static_cast<std::int64_t>(keep.size()),stair_budget);
        const std::int64_t step=divided>1?divided:1;
        const CastleModule& stair_mod=modules.at("wall_stair");
        std::vector<const CastleSegment*> picked;
        for(std::size_t i=0;i<keep.size();i+=static_cast<std::size_t>(step)) picked.push_back(&keep[i]);
        // keep[::step][:stair_budget], where a negative budget drops from the end.
        std::size_t take=picked.size();
        if(stair_budget>=0) take=std::min<std::size_t>(take,static_cast<std::size_t>(stair_budget));
        else {
            const auto dropped=static_cast<std::size_t>(-stair_budget);
            take=take>dropped?take-dropped:0;
        }
        for(std::size_t s_i=0;s_i<take;++s_i) {
            CastleJoinNode stair;
            stair.id=ring_id+"-stair-"+std::to_string(s_i);
            stair.ring_id=ring_id;
            stair.module_key="wall_stair";
            stair.module_id=stair_mod.id;
            stair.structure_id=stair_mod.structure_id;
            stair.position_m=picked[s_i]->center_m;
            stair.has_thickness=true;
            stair.thickness_m=thickness;
            stair.height_m=stair_mod.height_nominal;
            stair.has_curtain_height=true;
            stair.curtain_height_m=height;
            stair.walkway=true;
            stairs.push_back(stair);
        }
    }
    std::vector<CastleJoinNode> joins=gates;
    joins.insert(joins.end(),towers.begin(),towers.end());
    joins.insert(joins.end(),stairs.begin(),stairs.end());
    const std::vector<CastleJoinFailure> failures=validate_segment_chain(keep,joins,modules,rules);
    if(!failures.empty()) {
        for(const CastleJoinFailure& failure:failures) {
            CastleUnplaced unplaced;
            // `f.get('segment_id') or f.get('node_id')`: an id that is missing, or
            // present but empty, leaves the reference with None.
            unplaced.has_building_id=failure.has_id && !failure.id.empty();
            unplaced.building_id=unplaced.has_building_id?failure.id:std::string();
            unplaced.reason=failure.reason;
            report.unplaced.push_back(unplaced);
        }
        report.status="broken";
        report.segments=keep;
        report.nodes=vertices;
        report.gates=gates;
        report.towers=towers;
        report.stairs=stairs;
        return report;
    }
    report.status="closed";
    report.segments=keep;
    report.nodes=vertices;
    report.gates=gates;
    report.towers=towers;
    report.stairs=stairs;
    report.walkway_continuous=true;
    report.has_counts=true;
    report.segment_count=static_cast<std::int64_t>(keep.size());
    report.gate_count=static_cast<std::int64_t>(gates.size());
    report.ditch=ditch||ring_spec.ditch;
    return report;
}
}
