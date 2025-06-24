import unittest
from contracts import parse_json
class EnvelopeTests(unittest.TestCase):
    def test_depth_and_encoding_limits(self):
        for raw in (b'['*40+b'0'+b']'*40,b'['*2000+b'0'+b']'*2000,b'\xff'):
            with self.assertRaises(ValueError):parse_json(raw)
        self.assertEqual(parse_json(b'{"valid":[1,2]}'),{'valid':[1,2]})
    def test_duplicate_keys_in_nested_objects_rejected(self):
        with self.assertRaises(ValueError):parse_json(b'{"nested":{"a":1,"a":2}}')
