"""Bounded, pure counter proof. Durable transactions remain the host's job."""
import copy
from dataclasses import dataclass

from .kernel_contract import (KernelError, MAX_SAFE, MAX_BATCH, MAX_RECEIPTS, exact,
                              header, identifier, integer, version, validate_event, validate_command)
from .kernel_numeric import MAX_BYTES, canonical_bytes, canonical_loads


def _order(event):
    return event['time_ms'], event['event_id']


def initialize(world_id, authority_epoch=0):
    identifier(world_id, 'world')
    integer(authority_epoch, 'authority_epoch')
    return dict(schema='fantasy-world-generator.counter-state', schema_version=1, rules_version=1, numeric_version=1,
                world_id=world_id, authority_epoch=authority_epoch, revision=0, time_ms=0,
                counter=0, receipts=[], pending=None)


def validate_snapshot(state):
    exact(state, ('schema','schema_version','rules_version','numeric_version','world_id',
                  'authority_epoch','revision','time_ms','counter','receipts','pending'))
    header(state, 'fantasy-world-generator.counter-state')
    version(state['rules_version']); version(state['numeric_version'])
    identifier(state['world_id'], 'world')
    for key in ('authority_epoch','revision','time_ms','counter'):
        integer(state[key], key)
    receipts, pending = state['receipts'], state['pending']
    if type(receipts) is not list:
        raise KernelError('INVALID_INPUT', 'receipts must be an array')
    if len(receipts) > MAX_RECEIPTS:
        raise KernelError('STATE_CAPACITY', 'receipt limit exceeded')
    ceiling = state['time_ms']
    waiting = []
    if pending is not None:
        exact(pending, ('target_time_ms','events'))
        integer(pending['target_time_ms'], 'target_time_ms')
        waiting = pending['events']
        if pending['target_time_ms'] <= state['time_ms'] or type(waiting) is not list or not 1 <= len(waiting) <= MAX_BATCH:
            raise KernelError('INVALID_INPUT', 'invalid pending interval')
        ceiling = pending['target_time_ms']
    if len(receipts)+len(waiting) > MAX_RECEIPTS:
        raise KernelError('STATE_CAPACITY', 'pending receipts exceed retained capacity')
    seen, total, previous = set(), 0, None
    for receipt in receipts:
        exact(receipt, ('event','counter_after'))
        event = validate_event(receipt['event'], state['world_id'])
        key = _order(event)
        if event['event_id'] in seen or (previous is not None and key <= previous) or not 0 < event['time_ms'] <= ceiling:
            raise KernelError('INVALID_INPUT', 'receipt identity, order or time is invalid')
        seen.add(event['event_id']); previous = key
        total += event['delta']
        integer(total, 'counter total')
        integer(receipt['counter_after'], 'counter_after')
        if receipt['counter_after'] != total:
            raise KernelError('INVALID_INPUT', 'receipt accounting mismatch')
    if state['counter'] != total:
        raise KernelError('INVALID_INPUT', 'counter does not match retained effects')
    future_total = total
    for event in waiting:
        validate_event(event, state['world_id'])
        key = _order(event)
        if event['event_id'] in seen or (previous is not None and key <= previous) or not state['time_ms'] < event['time_ms'] <= ceiling:
            raise KernelError('INVALID_INPUT', 'pending identity, order or time is invalid')
        seen.add(event['event_id']); previous = key
        future_total += event['delta']
        integer(future_total, 'pending counter total')
    canonical_bytes(state)
    return copy.deepcopy(state)


def dump_snapshot(state):
    return canonical_bytes(validate_snapshot(state))


def load_snapshot(raw):
    return validate_snapshot(canonical_loads(raw))


@dataclass(frozen=True)
class Candidate:
    base_state: bytes
    command: bytes
    next_state: bytes
    effects: bytes
    work_used: int


def _candidate(base, command, state, effects, work):
    return Candidate(dump_snapshot(base), canonical_bytes(command), dump_snapshot(state),
                     canonical_bytes(effects), work)


def evaluate(snapshot, request):
    """Prepare at most budget new effects; never mutate the supplied snapshot."""
    state = validate_snapshot(snapshot)
    command = validate_command(request)
    if command['world_id'] != state['world_id']:
        raise KernelError('UNKNOWN_ID', 'command belongs to another world')
    if command['authority_epoch'] != state['authority_epoch']:
        raise KernelError('AUTHORITY_MISMATCH', 'command authority epoch is stale or unknown')
    unique = {}
    for event in command['events']:
        key = event['event_id']
        if key in unique and unique[key] != event:
            raise KernelError('CONFLICTING_EVENT', 'event ID reused with a different payload')
        unique[key] = event
    command['events'] = sorted(unique.values(), key=_order)
    received = {r['event']['event_id']: r['event'] for r in state['receipts']}
    pending = state['pending']
    waiting = [] if pending is None else pending['events']
    known = dict(received)
    known.update((event['event_id'], event) for event in waiting)
    for key, event in unique.items():
        if key in known and known[key] != event:
            raise KernelError('CONFLICTING_EVENT', 'event ID reused with a different payload')
    # A completed delivery retry can only acknowledge existing identical effects.
    if (pending is None and unique and all(key in received for key in unique)
            and command['target_time_ms'] <= state['time_ms']
            and command['expected_revision'] <= state['revision']):
        return _candidate(state, command, state, [], 0)
    if command['expected_revision'] != state['revision']:
        raise KernelError('STALE_REVISION', 'refresh the committed snapshot before evaluation')
    target = command['target_time_ms']
    if target < state['time_ms'] or (pending is not None and target != pending['target_time_ms']):
        raise KernelError('INTERVAL_CONFLICT', 'cannot rewind or replace a pending interval')
    if pending is not None:
        if any(key not in known for key in unique):
            raise KernelError('INTERVAL_CONFLICT', 'cannot insert work into an accepted pending interval')
    else:
        waiting = [event for event in command['events'] if event['event_id'] not in received]
        if any(not state['time_ms'] < event['time_ms'] <= target for event in waiting):
            raise KernelError('INTERVAL_CONFLICT', 'new events must lie inside (completed time, target time]')
    if len(state['receipts'])+len(waiting) > MAX_RECEIPTS:
        raise KernelError('STATE_CAPACITY', 'receipt retention is full; IDs cannot be forgotten or reused')
    if state['counter']+sum(event['delta'] for event in waiting) > MAX_SAFE:
        raise KernelError('NUMERIC_OVERFLOW', 'the complete interval exceeds the counter domain')
    work = min(command['budget'], len(waiting))
    result = copy.deepcopy(state)
    effects = []
    for event in waiting[:work]:
        result['counter'] += event['delta']
        receipt = {'event': copy.deepcopy(event), 'counter_after': result['counter']}
        result['receipts'].append(receipt)
        effects.append(receipt)
    remaining = waiting[work:]
    result['pending'] = {'target_time_ms': target, 'events': copy.deepcopy(remaining)} if remaining else None
    if not remaining:
        result['time_ms'] = target
    if result != state:
        if state['revision'] == MAX_SAFE:
            raise KernelError('NUMERIC_OVERFLOW', 'revision cannot wrap')
        result['revision'] += 1
    return _candidate(state, command, result, effects, work)


def commit(snapshot, candidate):
    """Validate portable commit data against the supplied current state; no I/O."""
    current = validate_snapshot(snapshot)
    if type(candidate) is not Candidate:
        raise KernelError('INVALID_CANDIDATE', 'expected an immutable candidate')
    if any(type(v) is not bytes or len(v) > MAX_BYTES for v in
           (candidate.base_state, candidate.command, candidate.next_state, candidate.effects)):
        raise KernelError('INVALID_CANDIDATE', 'candidate contains invalid byte envelopes')
    integer(candidate.work_used, 'work_used', maximum=MAX_BATCH, code='INVALID_CANDIDATE')
    try:
        expected = evaluate(load_snapshot(candidate.base_state), canonical_loads(candidate.command))
    except KernelError as error:
        raise KernelError('INVALID_CANDIDATE', 'candidate base or command is invalid') from error
    if candidate != expected:
        raise KernelError('INVALID_CANDIDATE', 'candidate does not match the independently re-evaluated transition')
    current_bytes = dump_snapshot(current)
    if current_bytes == candidate.next_state:
        return current  # An identical already-committed candidate is a no-op.
    if current_bytes != candidate.base_state:
        raise KernelError('STALE_REVISION', 'current state differs from the evaluated base')
    return load_snapshot(candidate.next_state)


def dump_candidate(candidate):
    if type(candidate) is not Candidate:
        raise KernelError('INVALID_CANDIDATE', 'expected an immutable candidate')
    base = load_snapshot(candidate.base_state)
    commit(base, candidate)
    return canonical_bytes(dict(schema='fantasy-world-generator.counter-candidate', schema_version=1,
                                base_state=base, command=canonical_loads(candidate.command),
                                next_state=canonical_loads(candidate.next_state),
                                effects=canonical_loads(candidate.effects), work_used=candidate.work_used))


def load_candidate(raw):
    document = canonical_loads(raw)
    exact(document, ('schema','schema_version','base_state','command','next_state','effects','work_used'))
    header(document, 'fantasy-world-generator.counter-candidate')
    candidate = Candidate(*(canonical_bytes(document[key]) for key in ('base_state','command','next_state','effects')),
                          work_used=document['work_used'])
    commit(document['base_state'], candidate)
    return candidate
