"""Independent byte/word fixtures for the new kernel, not legacy world RNG."""
import json
from pathlib import Path
import unittest

from fantasy_world_generator.kernel_numeric import canonical_bytes, canonical_loads, digest, random_word, unit_float
from fantasy_world_generator.kernel_contract import KernelError

ROOT = Path(__file__).resolve().parents[1]


class NumericTests(unittest.TestCase):
    def test_independent_vectors(self):
        vectors = json.loads((ROOT/'Fixtures/kernel-numeric-v1.json').read_text())
        for case in vectors['canonical']:
            with self.subTest(case=case):
                self.assertEqual(canonical_bytes(case['value']), case['ascii'].encode('ascii'))
                self.assertEqual(digest(case['value']), case['sha256'])
                self.assertEqual(canonical_loads(case['ascii'].encode()), case['value'])
        for case in vectors['streams']:
            self.assertEqual(random_word(case['seed'], case['stream'], case['index']), case['word'])
        self.assertEqual(unit_float('0000000000000000'), 0.)
        self.assertEqual(unit_float('8000000000000000'), .5)
        self.assertEqual(unit_float('ffffffffffffffff'), 1.-2**-53)

    def test_streams_have_no_global_state_or_call_order_coupling(self):
        first = [random_word('000000000000002a', 'ecology', i) for i in range(4)]
        for i in range(12):
            random_word('000000000000002a', 'cosmetics', i)
        self.assertEqual(first, [random_word('000000000000002a', 'ecology', i) for i in range(4)])
        self.assertEqual(first[::-1], [random_word('000000000000002a', 'ecology', i) for i in reversed(range(4))])

    def test_canonical_order_unicode_and_strict_numeric_domain(self):
        self.assertEqual(canonical_bytes({'z': 2, 'a': 1}), b'{"a":1,"z":2}')
        self.assertNotEqual(canonical_bytes([1, 2]), canonical_bytes([2, 1]))
        self.assertNotEqual(digest('\u00e9'), digest('e\u0301'))
        self.assertEqual(canonical_loads(b'-0'), 0)
        for value in (1., -0., float('nan'), float('inf'), 2**53, -(2**53), '\ud800', {1: 0}, b'x'):
            with self.subTest(value=repr(value)), self.assertRaises(KernelError):
                canonical_bytes(value)
        for raw in (b'{"a":1,"a":2}', b'1.0', b'NaN', b'9007199254740992', b'1'*1000, b'"\\ud800"', b'\xff', b'\xef\xbb\xbf{}'):
            with self.subTest(raw=raw[:30]), self.assertRaises(KernelError):
                canonical_loads(raw)
        cyclic=[]; cyclic.append(cyclic)
        for value in (cyclic, 'x'*4097, [0]*16385):
            with self.assertRaises(KernelError): canonical_bytes(value)

    def test_unknown_versions_and_stream_bounds(self):
        for version in (True, 1., '1', 0, 2):
            with self.assertRaises(KernelError): canonical_bytes({}, version=version)
            with self.assertRaises(KernelError): random_word('0000000000000000', 'terrain', 0, version=version)
        for seed, stream, index in [('0','terrain',0), ('FFFFFFFFFFFFFFFF','terrain',0), ('0'*16,'',0), ('0'*16,'Terrain',0), ('0'*16,'terrain',True), ('0'*16,'terrain',-1), ('0'*16,'terrain',2**53)]:
            with self.assertRaises(KernelError): random_word(seed, stream, index)
