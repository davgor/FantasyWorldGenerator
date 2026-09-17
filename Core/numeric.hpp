#pragma once
#include "json.hpp"
namespace fantasy_world_generator {
// Bounded contract hashing, not a cryptographic authentication API.
std::string sha256(const std::string& bytes);
std::string digest(const json::Value& value);
std::string random_word(const std::string& seed,const std::string& stream,std::int64_t index,std::int64_t version=1);
double unit_float(const std::string& word,std::int64_t version=1);
}
