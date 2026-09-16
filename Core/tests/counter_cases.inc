void require(bool condition) { if (!condition) throw std::runtime_error("native assertion failed"); }
template<class F> void expect_error(const std::string& code, F fn) {
    try { fn(); } catch (const Error& error) { require(error.code == code); return; }
    throw std::runtime_error("expected native failure: " + code);
}
int main() {
    try {
        /* SHARED_FIXTURES */
        require(initialize("world:demo") == initial);
        auto first = evaluate(initial, first_command);
        require(first.work_used == 1);
        require(commit(initial, first) == checkpoint);
        require(commit(checkpoint, first) == checkpoint);
        require(evaluate(initial, first_command) == first);
        auto reversed = first_command;
        std::reverse(reversed.events.begin(), reversed.events.end());
        require(evaluate(initial, reversed) == first);
        reversed.events.push_back(reversed.events.front());
        require(evaluate(initial, reversed) == first);
        require(commit(checkpoint, evaluate(checkpoint, resume_command)) == complete);
        auto altered = checkpoint; altered.counter = 999;
        Candidate bad{first.base_state, first.command, altered, first.effects, first.work_used};
        expect_error("INVALID_CANDIDATE", [&]{ commit(initial, bad); });
        auto conflict = first_command; conflict.events.push_back(conflict.events.front());
        conflict.events.back().delta += 1;
        expect_error("CONFLICTING_EVENT", [&]{ evaluate(initial, conflict); });
        auto stale = first_command; stale.expected_revision = 1;
        expect_error("STALE_REVISION", [&]{ evaluate(initial, stale); });
        stale = first_command; stale.authority_epoch = 1;
        expect_error("AUTHORITY_MISMATCH", [&]{ evaluate(initial, stale); });
        stale = resume_command; stale.target_time_ms = 20;
        expect_error("INTERVAL_CONFLICT", [&]{ evaluate(checkpoint, stale); });
        stale = resume_command; stale.events = first_command.events;
        stale.events[0].event_id = "event:new";
        expect_error("INTERVAL_CONFLICT", [&]{ evaluate(checkpoint, stale); });
        require(commit(complete, evaluate(complete, first_command)) == complete);
        stale = first_command; stale.expected_revision = complete.revision + 1;
        expect_error("STALE_REVISION", [&]{ evaluate(complete, stale); });
        for (int budget : {1, 2, 3}) {
            auto request = first_command; request.budget = budget;
            auto state = commit(initial, evaluate(initial, request));
            while (state.pending) {
                request = resume_command; request.expected_revision = state.revision; request.budget = budget;
                state = commit(state, evaluate(state, request));
            }
            require(state.counter == 10 && state.time_ms == 10 && state.receipts == complete.receipts);
        }
        auto overflow = first_command; overflow.events.resize(2);
        overflow.events[0].delta = max_safe; overflow.events[1].delta = 1;
        expect_error("NUMERIC_OVERFLOW", [&]{ evaluate(initial, overflow); });
        auto state = initial;
        for (int batch = 0; batch < 4; ++batch) {
            auto request = first_command; request.events.clear(); request.expected_revision = state.revision;
            request.budget = 64; request.target_time_ms = batch + 1;
            for (int i = 0; i < 64; ++i) {
                auto e = first_command.events[0]; e.event_id = "event:e" + std::to_string(batch*64+i);
                e.time_ms = batch + 1; e.delta = 1; request.events.push_back(e);
            }
            state = commit(state, evaluate(state, request));
        }
        require(state.counter == 256 && state.receipts.size() == 256);
        auto full = first_command; full.expected_revision = state.revision; full.events.resize(1);
        full.events[0].time_ms = 5; full.events[0].event_id = "event:overflow";
        expect_error("STATE_CAPACITY", [&]{ evaluate(state, full); });
        altered = checkpoint; altered.time_ms = 20;
        expect_error("INVALID_INPUT", [&]{ validate_snapshot(altered); });
        altered = initial; altered.schema_version = 2;
        expect_error("UNSUPPORTED_VERSION", [&]{ validate_snapshot(altered); });
        altered.schema_version = -1;
        expect_error("INVALID_INPUT", [&]{ validate_snapshot(altered); });
        altered.schema_version = max_safe+1;
        expect_error("INVALID_INPUT", [&]{ validate_snapshot(altered); });
        altered = initial; altered.revision = max_safe;
        stale = first_command; stale.expected_revision = max_safe;
        expect_error("NUMERIC_OVERFLOW", [&]{ evaluate(altered, stale); });
        stale = first_command; stale.events.resize(1); stale.events[0].delta = max_safe;
        require(commit(initial,evaluate(initial,stale)).counter == max_safe);
        altered = initial; altered.world_id = "world:bad\"";
        expect_error("INVALID_INPUT", [&]{ snapshot_json(altered); });
        altered = initial; altered.authority_epoch = 1;
        expect_error("STALE_REVISION", [&]{ commit(altered,first); });
        stale = first_command; stale.budget = 0;
        expect_error("WORK_BUDGET", [&]{ evaluate(initial,stale); });
        stale = first_command; stale.events[0].target_id = "counter:other";
        expect_error("UNKNOWN_ID", [&]{ evaluate(initial,stale); });
        std::cout << snapshot_json(checkpoint) << '\n' << snapshot_json(complete) << '\n';
        return 0;
    } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
