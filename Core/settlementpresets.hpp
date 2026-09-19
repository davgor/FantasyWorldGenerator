#pragma once
#include <cstdint>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
namespace fantasy_world_generator::settlementpresets {
// The settlement-preset slice of the civilization registry: the two shipped JSON
// catalogues are linked, validated once, and then expanded into the measured,
// unplaced requirement lists the city and hamlet planners consume.
//
// Two properties of the reference decide the shape of this port.
//
// First, the registry's identity is the sha256 of `json.dumps(doc, ensure_ascii=False,
// separators=(',',':'))` over the whole resolved document, so the port has to render
// every number exactly as Python's repr does and, crucially, has to walk every mapping
// in *insertion* order. A sorted container would produce a different identity and a
// different expanded plan, which is why `Value` carries an ordered field list rather
// than a std::map.
//
// Second, the reference rejects a broken catalogue with a specific English sentence
// and its callers read those sentences. The port raises the same sentence, and records
// which Python exception class carried it, because `section()` reaches the caller as a
// KeyError while everything else is a ValueError.
struct RegistryError : std::runtime_error {
    // "ValueError", "KeyError" or "OSError": the class CPython would have raised.
    std::string python_class;
    RegistryError(std::string python_class,const std::string& message)
        : std::runtime_error(message),python_class(std::move(python_class)) {}
};

// An insertion-ordered JSON value that keeps int and float apart.
//
// Core's catalogue reader collapses every number to a double, which is fatal here:
// Python writes `4` for an int and `4.0` for a float, both appear in these catalogues,
// and the difference lands in the registry sha256 and in every expanded plan.
struct Value {
    enum class Kind {Null,Bool,Int,Float,String,Array,Object};
    Kind kind=Kind::Null;
    bool boolean=false;
    double number=0.;
    std::int64_t whole=0;
    // True when the integer fits an int64; `text` then holds str(int). A literal too
    // wide for an int64 keeps its digits in `text` and only an approximation in
    // `number`, which is enough for the range tests this registry applies.
    bool whole_fits=false;
    // String payload, or the decimal spelling of an integer.
    std::string text;
    std::vector<Value> items;
    // Insertion order, exactly as a Python dict iterates.
    std::vector<std::pair<std::string,Value>> fields;

    bool is_object() const {return kind==Kind::Object;}
    bool is_array() const {return kind==Kind::Array;}
    bool is_string() const {return kind==Kind::String;}
    // `type(value) in (int,float)`: a bool is not a number, because `type(True)` is
    // `bool`. The registry leans on that distinction in half its range tests.
    bool is_number() const {return kind==Kind::Int||kind==Kind::Float;}
    const Value* find(const std::string& key) const;
    Value* find(const std::string& key);
    // `value[key]`, raising the KeyError the reference's callers catch.
    const Value& at(const std::string& key) const;
    // `value[key]=child`: replaces in place when the key exists, appends otherwise.
    void set(const std::string& key,Value child);
    bool has(const std::string& key) const {return find(key)!=nullptr;}
    static Value make_null();
    static Value make_bool(bool value);
    static Value make_int(std::int64_t value);
    static Value make_float(double value);
    static Value make_string(std::string value);
    static Value make_array();
    static Value make_object();
};
// `json.dumps(value, ensure_ascii=False, separators=(',',':'))`, which is how the
// registry's canonical bytes are produced before hashing.
std::string dumps(const Value& value);
// `json.loads(text, object_pairs_hook=_unique_object)`: a repeated key inside any one
// object is a fault, and the innermost offending object reports first, because the
// hook only runs when its object closes.
Value loads(const std::string& text);
// Python's `repr(float)` — the shortest decimal that reads back to the same double,
// switching to exponent form on Python's rule rather than %g's.
std::string py_repr(double value);

// The reference derives the registry path from `__file__`; a native build has none, so
// the host names the shipped civilizations.json once. `buildings.json` is read from
// beside it, as the reference's `with_name` does. Defaults to the repository layout
// relative to the working directory.
void set_registry_path(const std::string& path);
const std::string& registry_path();

// `_document()`: read, link, validate, cached on (path, modification time, size) as the
// reference's lru_cache is. The returned document is owned by the cache.
const Value& document();
// `load_registry()` / `section(name)`. Both deep-copy in the reference; the copies are
// what callers are allowed to mutate, so the port returns by value too.
Value load_registry();
Value section(const std::string& name);
// `_resolve(...)` over two catalogue texts, for callers that do not read from disk.
Value resolve(const std::string& registry_bytes,const std::string& buildings_bytes);
// `validate_registry(data)` in place, returning nothing; the reference returns `data`.
void validate_registry(const Value& data);

struct Identity {
    std::int64_t schema_version=0,revision=0;
    std::string sha256;
};
Identity registry_identity();
std::string default_profile_id();

// `staffing_totals(staff,count)`: unique roster posts, one resident worker each.
Value staffing_totals(const Value& staff,std::int64_t count);
// `city_plan` / `hamlet_plan`: an independent size preset resolved into measured,
// unplaced requirements. The city block must be one of the three authored sizes.
Value city_plan(const std::string& entity_id,const std::string& city_block);
Value hamlet_plan(const std::string& entity_id);
}
