#pragma once
#include <cstdint>
#include <map>
#include <string>
#include <variant>
#include <vector>
namespace fantasy_world_generator::catalogue {
// A reader for authoring data, deliberately separate from the kernel's JSON domain:
// catalogues carry real numbers, and the kernel contract forbids them on purpose.
// Bounds are generous because this parses a shipped table, not caller input.
constexpr std::size_t max_bytes=8388608, max_nodes=262144, max_depth=64, max_text_bytes=8192;
struct Value {
    using Array=std::vector<Value>;
    using Object=std::map<std::string,Value>;
    std::variant<std::nullptr_t,bool,double,std::string,Array,Object> data;
    Value() : data(nullptr) {}
};
Value parse(const std::string& bytes);
const Value::Object& object(const Value& value);
const Value::Array& array(const Value& value);
const std::string& text(const Value& value);
double number(const Value& value);
bool boolean(const Value& value);
bool is_null(const Value& value);
bool has(const Value& value,const std::string& key);
// Throws when the field is absent: a missing trait is a broken catalogue, not a default.
const Value& field(const Value& value,const std::string& key);
double number_or(const Value& value,const std::string& key,double fallback);
}
