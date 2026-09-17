#include "counter.hpp"
#include <algorithm>
#include <locale>
#include <map>
#include <set>
#include <sstream>
#include <utility>

namespace fantasy_world_generator {
namespace {
void check(bool valid, const char* code="INVALID_INPUT") { if (!valid) throw Error(code); }
void integer(std::int64_t n) { check(n >= 0 && n <= max_safe); }
void version(std::int64_t n) { integer(n); check(n == 1, "UNSUPPORTED_VERSION"); }
void header(const std::string& schema, std::int64_t v, const char* expected) {
    check(schema == expected, "UNSUPPORTED_VERSION"); version(v);
}
bool alnum(char c) { return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9'); }
void identifier(const std::string& id, const std::string& kind) {
    const auto prefix = kind + ":";
    check(id.size() > prefix.size() && id.size() <= prefix.size()+64 && id.compare(0,prefix.size(),prefix) == 0);
    check(alnum(id[prefix.size()]));
    for (auto i=prefix.size()+1; i<id.size(); ++i) check(alnum(id[i]) || id[i]=='.' || id[i]=='_' || id[i]=='-');
}
void event_valid(const Event& e, const std::string& world) {
    header(e.schema,e.schema_version,"fantasy-world-generator.counter-event");
    identifier(e.world_id,"world"); identifier(e.event_id,"event"); identifier(e.actor_id,"actor"); identifier(e.target_id,"counter");
    check(e.world_id == world && e.target_id == "counter:main", "UNKNOWN_ID");
    integer(e.time_ms); integer(e.delta); check(e.delta > 0);
}
auto order(const Event& e) { return std::make_pair(e.time_ms,e.event_id); }
std::int64_t add(std::int64_t a, std::int64_t b, const char* code="INVALID_INPUT") {
    check(b <= max_safe-a,code); return a+b;
}
void command_valid(const Command& c) {
    header(c.schema,c.schema_version,"fantasy-world-generator.counter-command"); identifier(c.world_id,"world");
    integer(c.authority_epoch); integer(c.expected_revision); integer(c.target_time_ms);
    check(c.budget >= 1 && c.budget <= 64,"WORK_BUDGET");
    check(c.events.size() <= 64,"STATE_CAPACITY");
    for (const auto& e:c.events) event_valid(e,c.world_id);
}
void event_json(std::ostream& out, const Event& e) {
    out << "{\"actor_id\":\"" << e.actor_id << "\",\"delta\":" << e.delta << ",\"event_id\":\"" << e.event_id
        << "\",\"schema\":\"fantasy-world-generator.counter-event\",\"schema_version\":1,\"target_id\":\"" << e.target_id
        << "\",\"time_ms\":" << e.time_ms << ",\"world_id\":\"" << e.world_id << "\"}";
}
}
Snapshot initialize(const std::string& world, std::int64_t epoch) {
    identifier(world,"world"); integer(epoch);
    Snapshot s; s.world_id=world; s.authority_epoch=epoch; return s;
}
void validate_event(const Event& event, const std::string& world_id) { event_valid(event,world_id); }
void validate_command(const Command& command) { command_valid(command); }
void validate_snapshot_header(const Snapshot& s) {
    header(s.schema,s.schema_version,"fantasy-world-generator.counter-state"); version(s.rules_version); version(s.numeric_version);
    identifier(s.world_id,"world"); integer(s.authority_epoch); integer(s.revision); integer(s.time_ms); integer(s.counter);
}
void validate_snapshot(const Snapshot& s) {
    validate_snapshot_header(s);
    check(s.receipts.size() <= 256,"STATE_CAPACITY");
    auto ceiling=s.time_ms;
    if (s.pending) {
        integer(s.pending->target_time_ms);
        check(s.pending->target_time_ms > s.time_ms && !s.pending->events.empty() && s.pending->events.size() <= 64);
        ceiling=s.pending->target_time_ms;
        check(s.receipts.size()+s.pending->events.size() <= 256,"STATE_CAPACITY");
    }
    std::set<std::string> seen;
    std::optional<std::pair<std::int64_t,std::string>> previous;
    std::int64_t total=0;
    auto inspect=[&](const Event& e, std::int64_t floor) {
        event_valid(e,s.world_id);
        auto key=order(e);
        check(seen.insert(e.event_id).second && (!previous || *previous < key) && e.time_ms > floor && e.time_ms <= ceiling);
        previous=key; total=add(total,e.delta);
    };
    for (const auto& r:s.receipts) { inspect(r.event,0); integer(r.counter_after); check(r.counter_after == total); }
    check(s.counter == total);
    if (s.pending) for (const auto& e:s.pending->events) inspect(e,s.time_ms);
}
Candidate evaluate(const Snapshot& state, const Command& request) {
    validate_snapshot(state); command_valid(request);
    check(request.world_id == state.world_id,"UNKNOWN_ID");
    check(request.authority_epoch == state.authority_epoch,"AUTHORITY_MISMATCH");
    Command command=request;
    std::map<std::string,Event> unique, received, known;
    for (const auto& e:command.events) {
        auto found=unique.find(e.event_id);
        check(found == unique.end() || found->second == e,"CONFLICTING_EVENT"); unique.insert_or_assign(e.event_id,e);
    }
    command.events.clear();
    for (const auto& item:unique) command.events.push_back(item.second);
    std::sort(command.events.begin(),command.events.end(),[](const Event& a,const Event& b){return order(a)<order(b);});
    for (const auto& r:state.receipts) received.emplace(r.event.event_id,r.event);
    known=received;
    std::vector<Event> waiting;
    if (state.pending) waiting=state.pending->events;
    for (const auto& e:waiting) known.emplace(e.event_id,e);
    bool all_received=!unique.empty();
    for (const auto& item:unique) {
        auto found=known.find(item.first);
        check(found == known.end() || found->second == item.second,"CONFLICTING_EVENT");
        all_received = all_received && received.count(item.first)>0;
    }
    if (!state.pending && all_received && command.target_time_ms <= state.time_ms && command.expected_revision <= state.revision)
        return {state,command,state,{},0};
    check(command.expected_revision == state.revision,"STALE_REVISION");
    auto target=command.target_time_ms;
    check(target >= state.time_ms && (!state.pending || target == state.pending->target_time_ms),"INTERVAL_CONFLICT");
    if (state.pending) {
        for (const auto& item:unique) check(known.count(item.first)>0,"INTERVAL_CONFLICT");
    } else {
        for (const auto& e:command.events) if (!received.count(e.event_id)) {
            check(state.time_ms < e.time_ms && e.time_ms <= target,"INTERVAL_CONFLICT"); waiting.push_back(e);
        }
    }
    check(state.receipts.size()+waiting.size() <= 256,"STATE_CAPACITY");
    auto total=state.counter;
    for (const auto& e:waiting) total=add(total,e.delta,"NUMERIC_OVERFLOW");
    auto work=std::min(static_cast<std::size_t>(command.budget),waiting.size());
    Snapshot result=state;
    std::vector<Receipt> effects;
    for (std::size_t i=0; i<work; ++i) {
        result.counter+=waiting[i].delta;
        Receipt receipt{waiting[i],result.counter}; result.receipts.push_back(receipt); effects.push_back(receipt);
    }
    if (work < waiting.size()) result.pending=Pending{target,{waiting.begin()+static_cast<std::ptrdiff_t>(work),waiting.end()}};
    else { result.pending.reset(); result.time_ms=target; }
    if (!(result == state)) result.revision=add(state.revision,1,"NUMERIC_OVERFLOW");
    validate_snapshot(result);
    return {state,command,result,effects,work};
}
Snapshot commit(const Snapshot& current, const Candidate& candidate) {
    validate_snapshot(current);
    try { check(candidate == evaluate(candidate.base_state,candidate.command),"INVALID_CANDIDATE"); }
    catch (const Error&) { throw Error("INVALID_CANDIDATE"); }
    if (current == candidate.next_state) return current;
    check(current == candidate.base_state,"STALE_REVISION");
    return candidate.next_state;
}
std::string snapshot_json(const Snapshot& s) {
    validate_snapshot(s);
    // Valid schemas and IDs are restricted to ASCII with no JSON escape characters.
    std::ostringstream out; out.imbue(std::locale::classic());
    out << "{\"authority_epoch\":" << s.authority_epoch << ",\"counter\":" << s.counter << ",\"numeric_version\":1,\"pending\":";
    if (s.pending) {
        out << "{\"events\":[";
        for (std::size_t i=0;i<s.pending->events.size();++i) { if(i) out << ','; event_json(out,s.pending->events[i]); }
        out << "],\"target_time_ms\":" << s.pending->target_time_ms << '}';
    } else out << "null";
    out << ",\"receipts\":[";
    for (std::size_t i=0;i<s.receipts.size();++i) {
        if(i) out << ',';
        out << "{\"counter_after\":" << s.receipts[i].counter_after << ",\"event\":"; event_json(out,s.receipts[i].event); out << '}';
    }
    out << "],\"revision\":" << s.revision << ",\"rules_version\":1,\"schema\":\"fantasy-world-generator.counter-state\",\"schema_version\":1,\"time_ms\":"
        << s.time_ms << ",\"world_id\":\"" << s.world_id << "\"}";
    return out.str();
}
}
