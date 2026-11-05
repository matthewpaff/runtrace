"""Cross-project recordings contain inert events from local synthetic workflows."""
import json
import unittest
from pathlib import Path

from evaluation import evaluate
from validation import validate


EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


class ExampleRecordingsTests(unittest.TestCase):
    def test_rental_booking_recording_has_confirmed_idempotent_effect(self):
        trace = json.loads((EXAMPLES / 'rental-booking.json').read_text(encoding='utf-8'))
        validate(trace)
        self.assertTrue(trace['synthetic'])
        self.assertEqual(evaluate(trace)['status'], 'pass')
        self.assertTrue(any(event.get('effect_id') for event in trace['events']))

    def test_document_approval_recording_has_scoped_consent(self):
        trace = json.loads((EXAMPLES / 'document-approval.json').read_text(encoding='utf-8'))
        validate(trace)
        self.assertTrue(trace['synthetic'])
        self.assertEqual(evaluate(trace)['status'], 'pass')
        self.assertTrue(any(event['kind'] == 'consent' for event in trace['events']))
