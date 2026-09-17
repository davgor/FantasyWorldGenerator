#pragma once
#include <cstddef>
#include <cstdint>
#include <optional>
#include <stdexcept>
#include <string>
#include <tuple>
#include <vector>

namespace fantasy_world_generator {
constexpr std::int64_t max_safe = 9007199254740991LL;
struct Error : std::runtime_error {
    std::string code;
    explicit Error(const std::string& value) : std::runtime_error(value), code(value) {}
};
struct Event {
    std::string schema; std::int64_t schema_version;
    std::string world_id, event_id, actor_id, target_id;
    std::int64_t time_ms, delta;
    bool operator==(const Event& b) const {
        return std::tie(schema,schema_version,world_id,event_id,actor_id,target_id,time_ms,delta) ==
               std::tie(b.schema,b.schema_version,b.world_id,b.event_id,b.actor_id,b.target_id,b.time_ms,b.delta);
    }
};
struct Receipt {
    Event event; std::int64_t counter_after;
    bool operator==(const Receipt& b) const { return event == b.event && counter_after == b.counter_after; }
};
struct Pending {
    std::int64_t target_time_ms; std::vector<Event> events;
    bool operator==(const Pending& b) const { return target_time_ms == b.target_time_ms && events == b.events; }
};
struct Snapshot {
    std::string schema = "fantasy-world-generator.counter-state";
    std::int64_t schema_version=1, rules_version=1, numeric_version=1;
    std::string world_id;
    std::int64_t authority_epoch=0, revision=0, time_ms=0, counter=0;
    std::vector<Receipt> receipts;
    std::optional<Pending> pending;
    bool operator==(const Snapshot& b) const {
        return std::tie(schema,schema_version,rules_version,numeric_version,world_id,authority_epoch,revision,time_ms,counter,receipts,pending) ==
               std::tie(b.schema,b.schema_version,b.rules_version,b.numeric_version,b.world_id,b.authority_epoch,b.revision,b.time_ms,b.counter,b.receipts,b.pending);
    }
};
struct Command {
    std::string schema; std::int64_t schema_version; std::string world_id;
    std::int64_t authority_epoch, expected_revision, target_time_ms, budget;
    std::vector<Event> events;
    bool operator==(const Command& b) const {
        return std::tie(schema,schema_version,world_id,authority_epoch,expected_revision,target_time_ms,budget,events) ==
               std::tie(b.schema,b.schema_version,b.world_id,b.authority_epoch,b.expected_revision,b.target_time_ms,b.budget,b.events);
    }
};
struct Candidate {
    const Snapshot base_state;
    const Command command;
    const Snapshot next_state;
    const std::vector<Receipt> effects;
    const std::size_t work_used;
    bool operator==(const Candidate& b) const {
        return base_state == b.base_state && command == b.command && next_state == b.next_state && effects == b.effects && work_used == b.work_used;
    }
};
Snapshot initialize(const std::string& world_id, std::int64_t authority_epoch=0);
void validate_snapshot(const Snapshot& state);
void validate_snapshot_header(const Snapshot& state);
void validate_event(const Event& event, const std::string& world_id);
void validate_command(const Command& command);
Candidate evaluate(const Snapshot& state, const Command& command);
Snapshot commit(const Snapshot& current, const Candidate& candidate);
std::string snapshot_json(const Snapshot& state);
}
