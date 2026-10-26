import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from transport import retry_read
from source_health import evaluate
from source_reader import PublicSession, SourceError


class TransportTests(unittest.TestCase):
    def test_transient_read_recovers_with_exactly_one_bounded_retry(self):
        for error in (TimeoutError('slow'), URLError(TimeoutError('slow')),
                      HTTPError('https://example.invalid', 522, 'timeout', {}, None)):
            read = Mock(side_effect=[error, 'verified'])
            sleep = Mock()
            self.assertEqual(retry_read(read, sleep), 'verified')
            self.assertEqual(read.call_count, 2)
            sleep.assert_called_once_with(2)

    def test_second_timeout_escapes_instead_of_retrying_forever(self):
        read = Mock(side_effect=TimeoutError('slow'))
        with self.assertRaises(TimeoutError):
            retry_read(read, Mock())
        self.assertEqual(read.call_count, 2)

    def test_denials_rate_limits_tls_and_parser_errors_never_retry(self):
        for error in (HTTPError('https://example.invalid', 403, 'denied', {}, None),
                      HTTPError('https://example.invalid', 429, 'rate limit', {}, None),
                      URLError('certificate verify failed'), SourceError('Source access denied'),
                      SourceError('Standings / completed matches disagree')):
            read = Mock(side_effect=error)
            with self.assertRaises(type(error)):
                retry_read(read, Mock())
            self.assertEqual(read.call_count, 1)

    def test_public_reader_uses_retry_without_altering_form_fields(self):
        session = PublicSession()
        fields = {'competition': '123'}
        with patch.object(session, '_send_once', side_effect=[TimeoutError(), 'document']) as read, patch('transport.time.sleep'):
            # Avoid a real delay while exercising the actual reader integration.
            with patch('source_reader.retry_read', side_effect=lambda fn: retry_read(fn, Mock())):
                self.assertEqual(session._send(session.source_url, fields), 'document')
        self.assertEqual(read.call_count, 2)
        read.assert_called_with(session.source_url, fields)


class HealthTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 10, 26, 8, tzinfo=timezone.utc)
        self.registry = [{'name': 'Antalya', 'last_error_kind': 'transport',
                          'last_checked_at': '2026-10-26T07:45:00+00:00'}]
        self.errors = [{'province': 'Antalya', 'error': 'timeout'}]

    def test_isolated_timeout_warns_then_alerts_once_after_45_minutes(self):
        clock = self.registry[0]['last_checked_at']
        for minutes, expected in ((0, []), (15, []), (30, []), (45, ['Antalya']), (60, [])):
            result = evaluate(self.registry, self.errors, (self.now + timedelta(minutes=minutes)).isoformat())
            self.assertEqual(result['alerts'], expected)
            self.assertEqual(self.registry[0]['last_checked_at'], clock)

    def test_validation_failure_alerts_once_and_recovery_rearms_it(self):
        self.registry[0]['last_error_kind'] = 'validation'
        self.assertEqual(evaluate(self.registry, self.errors, self.now.isoformat())['alerts'], ['Antalya'])
        self.assertEqual(evaluate(self.registry, self.errors, self.now.isoformat())['alerts'], [])
        evaluate(self.registry, [], self.now.isoformat())
        self.assertNotIn('first_error_at', self.registry[0])
        self.assertNotIn('error_alerted_at', self.registry[0])
        self.registry[0]['last_error_kind'] = 'validation'
        self.assertEqual(evaluate(self.registry, self.errors, self.now.isoformat())['alerts'], ['Antalya'])

    def test_widespread_transport_outage_alerts_immediately(self):
        registry = [{'name': str(i), 'last_error_kind': 'transport'} for i in range(4)]
        errors = [{'province': str(i), 'error': 'timeout'} for i in range(4)]
        self.assertEqual(len(evaluate(registry, errors, self.now.isoformat())['alerts']), 4)
        self.assertEqual(evaluate(registry, errors, self.now.isoformat())['alerts'], [])


if __name__ == '__main__':
    unittest.main()
