#pragma once
#include "counter.hpp"
#include <map>
#include <variant>
#include <utility>

namespace fantasy_world_generator::json {
constexpr std::size_t max_bytes=1048576, max_nodes=16384, max_depth=32, max_text_bytes=4096;
struct Value {
    using Array=std::vector<Value>;
    using Object=std::map<std::string,Value>;
    std::variant<std::nullptr_t,bool,std::int64_t,std::string,Array,Object> data;
    Value() : data(nullptr) {}
    explicit Value(bool v) : data(v) {}
    explicit Value(std::int64_t v) : data(v) {}
    explicit Value(std::string v) : data(std::move(v)) {}
    explicit Value(const char* v) : data(std::string(v)) {}
    explicit Value(Array v) : data(std::move(v)) {}
    explicit Value(Object v) : data(std::move(v)) {}
};
Value parse(const std::string& bytes);
std::string canonical(const Value& value);
const Value::Object& object(const Value& value);
const Value::Array& array(const Value& value);
const std::string& string(const Value& value);
std::int64_t integer(const Value& value);
bool is_null(const Value& value);
const Value& field(const Value& value,const std::string& key);
void exact(const Value& value,std::initializer_list<const char*> fields);
}
