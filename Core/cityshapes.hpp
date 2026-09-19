#pragma once
#include <cstdint>
#include <map>
#include <memory>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::cityshapes {
// Research-backed shape selection for the city-footprint planner: it picks a pattern
// and its parameters, and generates no coordinates. The port has to agree with the
// reference bit for bit because the chosen shape drives every later planner pass.
//
// The reference raises ValueError with a specific sentence for every rejection and
// callers read those sentences, so the port carries the sentence rather than a code.
struct ShapeError : std::runtime_error {
    explicit ShapeError(const std::string& message) : std::runtime_error(message) {}
};
// One site fact. The catalogue declares every feature either boolean or number, and
// the reference keeps the two apart by Python type, not by value; a bool handed to a
// numeric feature is a different rejection from an out-of-range number.
struct SiteValue {
    bool is_boolean=false;
    bool boolean=false;
    double number=0.;
};
inline SiteValue site_number(double value) {SiteValue v;v.number=value;return v;}
inline SiteValue site_boolean(bool value) {SiteValue v;v.is_boolean=true;v.boolean=value;return v;}
// Insertion-ordered, because the reference iterates `site.items()` and the first
// offending key decides which ValueError the caller sees. A sorted container would
// rank identically but could report a different fault.
using Site=std::vector<std::pair<std::string,SiteValue>>;
// One eligible alternative, in stable ID order. `rank` deliberately returns the whole
// weighted field rather than a forced winner.
struct Candidate {
    std::string id,family;
    double weight=0.;
    std::vector<std::string> matched_preferences;
};
// A drawn variation parameter. An `integer` range yields a Python int and every other
// range a float rounded to six decimals; the distinction survives into the plan's JSON,
// so the port keeps it too.
struct Parameter {
    bool integer=false;
    std::int64_t whole=0;
    double real=0.;
    double value() const {return integer?static_cast<double>(whole):real;}
};
// What `select_shape` returns. `has_shape` false is the reference's `shape_id: None`,
// which leaves `parameters`, `layout` and `source_ids` empty and only sets `reason`.
struct Selection {
    std::int64_t version=1;
    std::int64_t catalogue_revision=0;
    std::string catalogue_sha256;
    bool has_shape=false;
    std::string shape_id;
    std::map<std::string,Parameter> parameters;
    std::vector<Candidate> candidates;
    bool runtime_geometry_generated=false;
    std::string reason;
    std::map<std::string,std::string> layout;
    std::vector<std::string> source_ids;
};
// A validated city-shape catalogue. Immutable once built, which is what the reference
// buys with its `copy.deepcopy` of the cached parse.
class Catalogue {
  public:
    // `validate_catalogue(json.loads(bytes, object_pairs_hook=_unique))`: duplicate
    // object keys are a fault, not a last-one-wins merge.
    static Catalogue parse(const std::string& bytes);
    static Catalogue read(const std::string& path);
    std::int64_t revision() const;
    // sha256 of `json.dumps(data, sort_keys=True, separators=(',',':'))`. The seeded
    // draw mixes this in, so reproducing Python's repr of every float in the file is
    // part of the arithmetic contract, not a debugging nicety.
    const std::string& identity() const;
    const std::string& canonical_json() const;
    const std::string& family(const std::string& shape_id) const;
    std::vector<std::string> shape_ids() const;
    std::vector<Candidate> rank(const Site& site,const std::string& city_class="medium",
                                const std::map<std::string,std::int64_t>& nearby_counts={},
                                bool include_later=false) const;
    Selection select_shape(const Site& site,std::int64_t seed,const std::string& city_id,
                           const std::string& city_class="medium",
                           const std::map<std::string,std::int64_t>& nearby_counts={},
                           bool include_later=false) const;
  private:
    struct Document;
    std::shared_ptr<const Document> document_;
};
// The reference derives the catalogue path from `__file__`; a native build has no
// source path, so the host names the shipped file once. Defaults to the repository
// layout relative to the working directory.
void set_catalogue_path(const std::string& path);
const std::string& catalogue_path();
// Cached on (path, modification time, size), as the reference's lru_cache is.
const Catalogue& load_catalogue();
std::vector<Candidate> rank_shapes(const Site& site,const std::string& city_class="medium",
                                   const std::map<std::string,std::int64_t>& nearby_counts={},
                                   bool include_later=false);
Selection select_shape(const Site& site,std::int64_t seed,const std::string& city_id,
                       const std::string& city_class="medium",
                       const std::map<std::string,std::int64_t>& nearby_counts={},
                       bool include_later=false);
}
