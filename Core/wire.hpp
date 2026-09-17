#pragma once
#include "json.hpp"
namespace fantasy_world_generator {
Event event_value(const json::Value& value,const std::string& world_id);
Command command_value(const json::Value& value);
Snapshot snapshot_value(const json::Value& value);
Candidate candidate_value(const json::Value& value);
Snapshot parse_snapshot(const std::string& bytes);
Command parse_command(const std::string& bytes);
Candidate parse_candidate(const std::string& bytes);
std::string candidate_json(const Candidate& candidate);
std::string failure_json(const Error& error);
}
