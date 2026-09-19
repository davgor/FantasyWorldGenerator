#pragma once
#include "globe.hpp"
#include <array>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::sceneframe {
// The one globe coordinate boundary every local planner shares (world_scene.frame,
// world_scene.local_direction and world_scene.road_entries).
//
// The city, hamlet and castle planners all run this before any of them has a plan, so
// the tangent basis and the road gates it derives have to agree with the reference to
// the last bit or three planners drift apart at once.
//
// NOTE: this frame is deliberately NOT terrain_globe.direction. The reference builds
// `up` straight from the site's latitude and longitude with no pole special case and
// no longitude wrap, so at z==0 it is (6.12e-17, 1, 7.50e-33) rather than (0, 1, 0),
// and at x==n-1 it is the +pi seam rather than direction's -pi. Route nodes on line 33
// of the reference DO go through terrain_globe.direction, so the two conventions meet
// inside road_entries and the difference is real, not a rounding artefact. Core's
// direction() is reused for the nodes and must not be reused for the frame.

// The reference raises out of Python arithmetic rather than returning a sentinel, and
// callers let those propagate, so the port raises too and keeps CPython's wording.
struct ZeroDivision : std::domain_error {
    ZeroDivision() : std::domain_error("float division by zero") {}
};
struct IndexError : std::out_of_range {
    IndexError() : std::out_of_range("list index out of range") {}
};

// `r, up, east, north` of the reference's four-tuple.
struct Frame {
    double radius=0.;
    Vec3 up{},east{},north{};
};

// A settlement identity as `site.get('uid', site['id'])` yields it. The reference
// compares those values with `==`, and a Python int never equals a Python str, so an
// integer id and its decimal spelling are two different settlements. Keeping the tag
// is what stops the port matching a site the reference would have missed.
struct Identity {
    bool is_text=false;
    std::int64_t number=0;
    std::string text;
    bool operator==(const Identity& other) const {
        if(is_text!=other.is_text) return false;
        return is_text?text==other.text:number==other.number;
    }
    // How an f-string interpolates it, which is what junction ids are built from.
    std::string label() const {return is_text?text:std::to_string(number);}
};
inline Identity identity_number(std::int64_t value) {Identity id;id.number=value;return id;}
inline Identity identity_text(std::string value) {
    Identity id;id.is_text=true;id.text=std::move(value);return id;
}

// Grid column and row of the site, which the reference reads as `site['x']` and
// `site['z']`. Hamlet and castle plans pass their own dict, so these are not always
// the settlement list's own entry.
struct Site {
    double x=0.,z=0.;
    Identity id;
};

// One entry of `world['roads']['routes']`. `nodes` indexes `world['water']['nodes']`.
struct Route {
    std::int64_t from=0,to=0;
    std::vector<std::int64_t> nodes;
};

// The slice of the world envelope these three helpers read. `site_ids` is
// `world['settlements']['sites']` already reduced to the identity the reference
// compares, in list order, because only the order and the identities matter here.
struct World {
    std::int64_t size=0;
    double config_globe_radius=0.;
    // `world.get('effective_config', world['config'])['globe_radius']`: the physical
    // radius wins when the envelope carries one, the requested radius otherwise.
    bool has_effective_config=false;
    double effective_globe_radius=0.;
    std::vector<std::pair<std::int64_t,std::int64_t>> water_nodes;
    std::vector<Identity> site_ids;
    std::vector<Route> routes;
    double globe_radius() const {
        return has_effective_config?effective_globe_radius:config_globe_radius;
    }
};

// One regional road meeting one settlement window. Every entry the reference emits is
// 'unreachable': it records where the route crosses the window edge so the street
// planner can try to reach it, and says nothing about whether the street planner will.
struct RoadEntry {
    std::string route_id;
    std::int64_t route_index=0;
    std::string end;                 // 'from' or 'to'
    std::int64_t outside_index=0;    // index into the route's own node order
    std::string junction_id;
    std::array<double,2> gate_local_m{};
    Vec3 direction{};
    std::string status,reason;
};

// Tangent basis at a site, in metres. Raises ZeroDivision when size is one.
Frame frame(const World& world,const Site& site);
// Unit globe direction of a local east/north offset in metres.
Vec3 local_direction(const Frame& f,double x,double z);
// Where each regional road touching this site crosses the square window of half-width
// `half` metres, walking outward from the settlement.
//
// Two ways out of the walk emit nothing for a route: the node list running out before
// the window edge, and a node falling behind the tangent plane. The second is the
// reference's `if den<=0: break` horizon guard -- it abandons the whole route, it does
// not skip the node, so a route that dips over the horizon before it leaves the window
// contributes no gate at all.
std::vector<RoadEntry> road_entries(const World& world,const Site& site,double half);
}
