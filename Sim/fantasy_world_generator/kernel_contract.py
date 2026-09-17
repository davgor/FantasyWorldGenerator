"""Strict version-1 envelopes for the bounded counter proof."""
import copy
import re

MAX_SAFE = 2**53 - 1
MAX_BATCH = 64
MAX_RECEIPTS = 256


class KernelError(ValueError):
    """Stable code with diagnostic, non-contractual human-readable text."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)

    def document(self):
        return {'schema': 'fantasy-world-generator.failure', 'schema_version': 1,
                'code': self.code, 'message': str(self)}


def integer(value, name, minimum=0, maximum=MAX_SAFE, code='INVALID_INPUT'):
    if type(value) is not int or not minimum <= value <= maximum:
        raise KernelError(code, name + ' must be an integer in the declared range')
    return value


def identifier(value, kind):
    if type(value) is not str or re.fullmatch(re.escape(kind)+r':[a-z0-9][a-z0-9._-]{0,63}', value) is None:
        raise KernelError('INVALID_INPUT', 'invalid ' + kind + ' identity')
    return value


def version(value):
    integer(value, 'version')
    if value != 1:
        raise KernelError('UNSUPPORTED_VERSION', 'only contract version 1 is supported')


def exact(value, fields):
    if type(value) is not dict or set(value) != set(fields):
        raise KernelError('INVALID_INPUT', 'unexpected or missing envelope fields')


def header(value, schema):
    if value['schema'] != schema:
        raise KernelError('UNSUPPORTED_VERSION', 'unsupported schema identity')
    version(value['schema_version'])


def validate_event(event, world_id):
    exact(event, ('schema','schema_version','world_id','event_id','actor_id','target_id','time_ms','delta'))
    header(event, 'fantasy-world-generator.counter-event')
    identifier(event['world_id'], 'world')
    identifier(event['event_id'], 'event')
    identifier(event['actor_id'], 'actor')
    identifier(event['target_id'], 'counter')
    if event['world_id'] != world_id or event['target_id'] != 'counter:main':
        raise KernelError('UNKNOWN_ID', 'world or target is not owned by this snapshot')
    integer(event['time_ms'], 'time_ms')
    integer(event['delta'], 'delta', minimum=1)
    return copy.deepcopy(event)


def validate_command(command):
    exact(command, ('schema','schema_version','world_id','authority_epoch','expected_revision','target_time_ms','budget','events'))
    header(command, 'fantasy-world-generator.counter-command')
    identifier(command['world_id'], 'world')
    for key in ('authority_epoch','expected_revision','target_time_ms'):
        integer(command[key], key)
    integer(command['budget'], 'budget', minimum=1, maximum=MAX_BATCH, code='WORK_BUDGET')
    if type(command['events']) is not list:
        raise KernelError('INVALID_INPUT', 'events must be an array')
    if len(command['events']) > MAX_BATCH:
        raise KernelError('STATE_CAPACITY', 'a command accepts at most 64 event entries')
    for event in command['events']:
        validate_event(event, command['world_id'])
    return copy.deepcopy(command)
