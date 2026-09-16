#include "wire.hpp"

namespace mathlab {
namespace {
using json::Value;
const Value& get(const Value& v,const char* key) {return json::field(v,key);}
std::int64_t number(const Value& v,const char* key) {return json::integer(get(v,key));}
const std::string& text(const Value& v,const char* key) {return json::string(get(v,key));}
void header(const Value& v,const char* expected) {
    const auto& schema=get(v,"schema");auto p=std::get_if<std::string>(&schema.data);
    if(!p || *p!=expected) throw Error("UNSUPPORTED_VERSION");
    auto version=number(v,"schema_version");
    if(version<0) throw Error("INVALID_INPUT");
    if(version!=1) throw Error("UNSUPPORTED_VERSION");
}
Value event_document(const Event& e) {
    return Value(Value::Object{{"schema",Value(e.schema)},{"schema_version",Value(e.schema_version)},
        {"world_id",Value(e.world_id)},{"event_id",Value(e.event_id)},{"actor_id",Value(e.actor_id)},
        {"target_id",Value(e.target_id)},{"time_ms",Value(e.time_ms)},{"delta",Value(e.delta)}});
}
Value receipt_document(const Receipt& r) {return Value(Value::Object{{"event",event_document(r.event)},{"counter_after",Value(r.counter_after)}});}
Value command_document(const Command& c) {
    Value::Array events;for(const auto& e:c.events) events.push_back(event_document(e));
    return Value(Value::Object{{"schema",Value(c.schema)},{"schema_version",Value(c.schema_version)},
        {"world_id",Value(c.world_id)},{"authority_epoch",Value(c.authority_epoch)},
        {"expected_revision",Value(c.expected_revision)},{"target_time_ms",Value(c.target_time_ms)},
        {"budget",Value(c.budget)},{"events",Value(std::move(events))}});
}
Receipt receipt_value(const Value& value,const std::string& world) {
    json::exact(value,{"event","counter_after"});
    return Receipt{event_value(get(value,"event"),world),number(value,"counter_after")};
}
}
Event event_value(const json::Value& value,const std::string& world_id) {
    json::exact(value,{"schema","schema_version","world_id","event_id","actor_id","target_id","time_ms","delta"});
    header(value,"mathlab.counter-event");
    Event result{text(value,"schema"),number(value,"schema_version"),text(value,"world_id"),text(value,"event_id"),
                 text(value,"actor_id"),text(value,"target_id"),number(value,"time_ms"),number(value,"delta")};
    validate_event(result,world_id);return result;
}
Command command_value(const json::Value& value) {
    json::exact(value,{"schema","schema_version","world_id","authority_epoch","expected_revision","target_time_ms","budget","events"});
    header(value,"mathlab.counter-command");
    std::int64_t budget=0;
    try {budget=number(value,"budget");if(budget<1 || budget>64) throw Error("WORK_BUDGET");}
    catch(const Error&) {throw Error("WORK_BUDGET");}
    Command result{text(value,"schema"),number(value,"schema_version"),text(value,"world_id"),number(value,"authority_epoch"),
                   number(value,"expected_revision"),number(value,"target_time_ms"),budget,{}};
    validate_command(result);
    const auto& events=json::array(get(value,"events"));
    if(events.size()>64) throw Error("STATE_CAPACITY");
    for(const auto& event:events) result.events.push_back(event_value(event,result.world_id));
    validate_command(result);return result;
}
Snapshot snapshot_value(const json::Value& value) {
    json::exact(value,{"schema","schema_version","rules_version","numeric_version","world_id","authority_epoch","revision","time_ms","counter","receipts","pending"});
    header(value,"mathlab.counter-state");
    Snapshot result;
    result.schema=text(value,"schema");result.schema_version=number(value,"schema_version");
    result.rules_version=number(value,"rules_version");result.numeric_version=number(value,"numeric_version");
    result.world_id=text(value,"world_id");result.authority_epoch=number(value,"authority_epoch");
    result.revision=number(value,"revision");result.time_ms=number(value,"time_ms");result.counter=number(value,"counter");
    validate_snapshot_header(result);
    const auto& receipts=json::array(get(value,"receipts"));
    if(receipts.size()>256) throw Error("STATE_CAPACITY");
    for(const auto& receipt:receipts) result.receipts.push_back(receipt_value(receipt,result.world_id));
    const auto& pending=get(value,"pending");
    if(!json::is_null(pending)) {
        json::exact(pending,{"target_time_ms","events"});
        Pending p{number(pending,"target_time_ms"),{}};
        const auto& events=json::array(get(pending,"events"));
        if(events.empty() || events.size()>64) throw Error("INVALID_INPUT");
        for(const auto& event:events) p.events.push_back(event_value(event,result.world_id));
        result.pending=std::move(p);
    }
    validate_snapshot(result);return result;
}
Candidate candidate_value(const json::Value& value) {
    json::exact(value,{"schema","schema_version","base_state","command","next_state","effects","work_used"});
    header(value,"mathlab.counter-candidate");
    auto base=snapshot_value(get(value,"base_state"));
    try {
        auto command=command_value(get(value,"command"));
        auto next=snapshot_value(get(value,"next_state"));
        auto work=number(value,"work_used");if(work<0 || work>64) throw Error("INVALID_CANDIDATE");
        std::vector<Receipt> effects;
        const auto& items=json::array(get(value,"effects"));
        if(items.size()>64) throw Error("INVALID_CANDIDATE");
        for(const auto& receipt:items) effects.push_back(receipt_value(receipt,base.world_id));
        Candidate candidate{base,command,next,effects,static_cast<std::size_t>(work)};
        commit(base,candidate);return candidate;
    } catch(const Error&) {throw Error("INVALID_CANDIDATE");}
}
Snapshot parse_snapshot(const std::string& bytes) {return snapshot_value(json::parse(bytes));}
Command parse_command(const std::string& bytes) {return command_value(json::parse(bytes));}
Candidate parse_candidate(const std::string& bytes) {return candidate_value(json::parse(bytes));}
std::string candidate_json(const Candidate& candidate) {
    commit(candidate.base_state,candidate);
    Value::Array effects;for(const auto& r:candidate.effects) effects.push_back(receipt_document(r));
    return json::canonical(Value(Value::Object{{"schema",Value("mathlab.counter-candidate")},{"schema_version",Value(std::int64_t{1})},
        {"base_state",json::parse(snapshot_json(candidate.base_state))},{"command",command_document(candidate.command)},
        {"next_state",json::parse(snapshot_json(candidate.next_state))},{"effects",Value(std::move(effects))},
        {"work_used",Value(static_cast<std::int64_t>(candidate.work_used))}}));
}
std::string failure_json(const Error& error) {
    return json::canonical(Value(Value::Object{{"schema",Value("mathlab.failure")},{"schema_version",Value(std::int64_t{1})},
                                              {"code",Value(error.code)},{"message",Value(error.what())}}));
}
}
