import copy
import importlib.util
import io
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'reclip_api.py'
spec = importlib.util.spec_from_file_location('reclip_api', SCRIPT)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
ID = '00000000-0000-4000-8000-000000000001'
JOB = '00000000-0000-4000-8000-000000000002'
BODY = {'tool': 'mp4_to_mp3', 'input': {'asset_id': ID, 'file_name': 'source.mp4', 'operation': 'extract_mp3'}, 'maximum_credits': 20}


class Response(io.BytesIO):
    def __init__(self, value):
        super().__init__(value if isinstance(value, bytes) else json.dumps(value).encode())


class Transport:
    def __init__(self, *values):
        self.values, self.requests = list(values), []

    def open(self, request, timeout):
        self.requests.append(request)
        value = self.values.pop(0)
        if isinstance(value, Exception):
            raise value
        if hasattr(request.data, 'read'):
            self.uploaded = request.data.read()
        return Response(value)


def http_error(code, headers=None, body=None):
    return urllib.error.HTTPError('https://example.test', code, 'failure', headers or {}, Response(body or {'error': {'code': 'test_error'}, 'request_id': 'req-1'}))


class FakeAPI:
    base = a.DEFAULT_BASE

    def __init__(self):
        self.calls = []
        self.key_id = 'key-1'
        self.estimate = 10
        self.boom = False
        self.seconds = 0
        self.statuses = ['succeeded']
        self.confirmed = False
        self.size = 4

    def clock(self):
        return self.seconds

    def sleep(self, seconds):
        self.seconds += seconds

    def call(self, operation, resource=None, data=None, **kwargs):
        self.calls.append((operation, resource, copy.deepcopy(data), kwargs))
        if operation == 'identity':
            return {'workspace_id': 'workspace-1', 'key_id': self.key_id}
        if operation == 'quote':
            return {'estimated_credits': self.estimate, 'affordable': True}
        if operation in {'submit', 'export-clip'}:
            if self.boom:
                raise a.ClientError('uncertain outcome')
            return {'id': JOB, 'replayed': False}
        if operation == 'status':
            if kwargs.get('deadline', float('inf')) <= self.seconds:
                raise a.ClientError('Polling timeout')
            status = self.statuses.pop(0) if len(self.statuses) > 1 else self.statuses[0]
            return {'id': JOB, 'status': status, 'outputs': [{'asset_id': ID}]}
        if operation == 'upload-intent':
            return {'asset_id': ID, 'method': 'PUT', 'upload_url': 'https://storage.example.test/upload?signature=secret', 'expires_at': '2099-01-01T00:00:00Z', 'headers': {'Content-Type': 'video/mp4'}}
        if operation == 'confirm':
            if not self.confirmed:
                self.confirmed = True
                raise a.ApiError(409)
            return {'asset_id': ID, 'state': 'ready'}
        if operation == 'asset':
            return {'id': ID, 'state': 'ready', 'size_bytes': self.size}
        if operation == 'download-url':
            return {'url': 'https://storage.example.test/download?signature=secret'}
        return {}


class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'run.state.json'
        self.api = FakeAPI()

    def test_replay_does_not_requote_or_resubmit(self):
        a.submit_saved(self.api, 'submit', BODY, self.path)
        result = a.submit_saved(self.api, 'submit', BODY, self.path)
        self.assertTrue(result['replayed'])
        self.assertEqual([c[0] for c in self.api.calls].count('submit'), 1)
        self.assertEqual([c[0] for c in self.api.calls].count('quote'), 1)

    def test_uncertain_submission_reuses_persisted_key(self):
        self.api.boom = True
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', BODY, self.path)
        key = a.read_json(self.path, state=True)['idempotency_key']
        self.api.boom = False
        a.submit_saved(self.api, 'submit', BODY, self.path)
        keys = [c[3]['idempotency'] for c in self.api.calls if c[0] == 'submit']
        self.assertEqual(keys, [key, key])

    def test_changed_request_rejected(self):
        a.submit_saved(self.api, 'submit', BODY, self.path)
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', dict(BODY, maximum_credits=30), self.path)

    def test_rotated_identity_rejected(self):
        a.submit_saved(self.api, 'submit', BODY, self.path)
        self.api.key_id = 'key-2'
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', BODY, self.path)

    def test_changed_base_rejected(self):
        a.submit_saved(self.api, 'submit', BODY, self.path)
        self.api.base = 'https://other.example.test/api/v1'
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', BODY, self.path)

    def test_over_budget_never_submits(self):
        self.api.estimate = 21
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', BODY, self.path)
        self.assertFalse(self.path.exists())
        self.assertNotIn('submit', [c[0] for c in self.api.calls])

    def test_invalid_quote_never_submits(self):
        self.api.estimate = float('nan')
        with self.assertRaises(a.ClientError):
            a.submit_saved(self.api, 'submit', BODY, self.path)
        self.assertFalse(self.path.exists())

    def test_large_valid_request_state_can_resume(self):
        payload = dict(BODY, input={'text': 'x' * 230000})
        a.submit_saved(self.api, 'submit', payload, self.path)
        self.assertTrue(a.submit_saved(self.api, 'submit', payload, self.path)['replayed'])

    def test_exports_use_revision_without_invented_quote(self):
        a.submit_saved(self.api, 'export-clip', {'editor_revision': 2}, self.path, ID)
        self.assertNotIn('quote', [c[0] for c in self.api.calls])
        self.assertEqual(self.api.calls[-1][2], {'editor_revision': 2})

    @unittest.skipIf(os.name == 'nt', 'POSIX advisory lock test')
    def test_parallel_state_is_rejected(self):
        with a.locked_state(self.path):
            with self.assertRaises(a.ClientError):
                with a.locked_state(self.path):
                    self.fail('acquired duplicate lock')

    def test_wait_success_and_failure(self):
        self.api.statuses = ['queued', 'running', 'succeeded']
        self.assertEqual(a.wait_job(self.api, JOB, 20, 2)['status'], 'succeeded')
        self.assertEqual(self.api.seconds, 4)
        for status in ['failed', 'canceled', 'unknown']:
            self.api.statuses = [status]
            with self.assertRaises(a.ClientError):
                a.wait_job(self.api, JOB)
        self.assertNotIn('submit', [c[0] for c in self.api.calls])

    def test_wait_timeout_bounded(self):
        self.api.statuses = ['running']
        with self.assertRaises(a.ClientError):
            a.wait_job(self.api, JOB, 3, 2)
        self.assertEqual(self.api.seconds, 3)

    def test_upload_resume_and_no_storage_bearer(self):
        source = Path(self.tmp.name) / 'source.mp4'
        source.write_bytes(b'data')
        storage = Transport(b'')
        a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=storage)
        self.assertEqual(storage.uploaded, b'data')
        self.assertFalse(storage.requests[0].has_header('Authorization'))
        self.assertNotIn('signature', self.path.read_text())
        a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=storage)
        self.assertEqual(len(storage.requests), 1)
        self.assertEqual([c[0] for c in self.api.calls].count('upload-intent'), 1)
        source.write_bytes(b'new!')
        with self.assertRaises(a.ClientError):
            a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=storage)

    def test_interrupted_upload_confirms_same_asset_on_resume(self):
        source = Path(self.tmp.name) / 'source.mp4'
        source.write_bytes(b'data')
        with self.assertRaises(a.ClientError):
            a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=Transport(urllib.error.URLError('lost response')))
        result = a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=Transport())
        self.assertEqual(result['asset_id'], ID)
        self.assertEqual([c[0] for c in self.api.calls].count('upload-intent'), 1)

    def test_expired_upload_does_not_create_replacement(self):
        source = Path(self.tmp.name) / 'source.mp4'
        source.write_bytes(b'data')
        with self.assertRaises(a.ClientError):
            a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=Transport(urllib.error.URLError('lost response')))
        state = a.read_json(self.path, state=True)
        state['authorization']['expires_at'] = '2000-01-01T00:00:00Z'
        a.save_state(self.path, state)
        self.api.confirmed = False
        with self.assertRaisesRegex(a.ClientError, 'expired'):
            a.upload(self.api, source, 'mp4_to_mp3', self.path, opener=Transport())
        self.assertEqual([c[0] for c in self.api.calls].count('upload-intent'), 1)

    def test_run_command_resume_end_to_end(self):
        request = Path(self.tmp.name) / 'request.json'
        request.write_text(json.dumps(BODY))
        args = a.parser().parse_args(['run', str(request), '--state', str(self.path), '--maximum-credits', '20'])
        self.api.statuses = ['queued', 'succeeded']
        result = a.execute(args, self.api)
        self.assertEqual(result['outputs'][0]['asset_id'], ID)
        a.execute(args, self.api)
        self.assertEqual([c[0] for c in self.api.calls].count('submit'), 1)

    def test_download_atomic_no_storage_bearer(self):
        storage = Transport(b'data')
        a.download(self.api, ID, self.path, opener=storage)
        self.assertEqual(self.path.read_bytes(), b'data')
        self.assertFalse(storage.requests[0].has_header('Authorization'))
        with self.assertRaises(a.ClientError):
            a.download(self.api, ID, self.path, opener=storage)
        self.assertEqual(self.path.read_bytes(), b'data')

    def test_download_mismatch_and_limit_discard_partial(self):
        for value in [b'bad', b'longer']:
            with self.assertRaises(a.ClientError):
                a.download(self.api, ID, self.path, max_bytes=4, opener=Transport(value))
            self.assertFalse(self.path.exists())


class TransportTests(unittest.TestCase):
    def test_real_http_redirect_is_not_followed(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(302)
                self.send_header('Location', '/would-leak-credentials')
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = a.Client(base='http://127.0.0.1:{}/api/v1'.format(server.server_port), key='test-key')
            with self.assertRaises(a.ApiError) as error:
                client.call('identity')
            self.assertEqual(error.exception.status, 302)
            self.assertEqual(received, ['/api/v1/me'])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_auth_stays_on_configured_origin(self):
        t = Transport({'workspace_id': 'w'})
        a.Client(key='test-key', opener=t).call('identity')
        self.assertEqual(t.requests[0].full_url, a.DEFAULT_BASE + '/me')
        self.assertEqual(t.requests[0].get_header('Authorization'), 'Bearer test-key')
        self.assertIsNone(a.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example'))

    def test_transient_submit_reuses_body_and_key(self):
        t = Transport(http_error(503), {'id': JOB})
        delays = []
        a.Client(key='test-key', opener=t, sleep=delays.append).call('submit', data=BODY, idempotency='request-001')
        self.assertEqual(delays, [1])
        self.assertEqual(t.requests[0].data, t.requests[1].data)
        self.assertEqual(t.requests[0].get_header('Idempotency-key'), t.requests[1].get_header('Idempotency-key'))

    def test_retry_after_respected(self):
        t = Transport(http_error(429, {'Retry-After': '7'}), {})
        delays = []
        a.Client(key='test-key', opener=t, sleep=delays.append).call('usage')
        self.assertEqual(delays, [7])
        with self.assertRaises(a.ClientError):
            a.retry_seconds('120', 0)

    def test_nonidempotent_create_not_retried(self):
        t = Transport(http_error(503))
        with self.assertRaises(a.ApiError):
            a.Client(key='test-key', opener=t).call('create-project', data={'title': 'X'})
        self.assertEqual(len(t.requests), 1)

    def test_error_body_not_echoed(self):
        t = Transport(http_error(400, body={'error': {'code': 'bad request SECRET', 'message': 'SECRET'}, 'request_id': 'bad SECRET'}))
        with self.assertRaises(a.ApiError) as error:
            a.Client(key='SECRET', opener=t).call('identity')
        self.assertNotIn('SECRET', str(error.exception))

    def test_allowlist_and_paths(self):
        client = a.Client(key='test-key', opener=Transport())
        for operation, resource in [('https://evil.example', None), ('asset', '../../me'), ('tool', 'gemini_watermark_remover')]:
            with self.assertRaises(a.ClientError):
                client.call(operation, resource)
        with self.assertRaises(a.ClientError):
            client.call('submit', data=BODY)

    def test_invalid_base_and_storage_urls(self):
        for url in ['http://example.com/api/v1', 'https://a:b@example.com/api/v1', 'https://example.com/api/v1?q=x', 'https://example.com/other']:
            with self.assertRaises(a.ClientError):
                a.base_url(url)
        self.assertEqual(a.base_url('http://localhost:8000/api/v1'), 'http://localhost:8000/api/v1')
        for url in ['http://example.com/file', 'https://key@example.com/file']:
            with self.assertRaises(a.ClientError):
                a.storage_url(url)

    def test_response_bounds_and_bad_json(self):
        with self.assertRaises(a.ClientError):
            a.read_response(Response(b'not-json'))
        with patch.object(a, 'MAX_RESPONSE', 4):
            with self.assertRaises(a.ClientError):
                a.read_response(Response(b'{"a":1}'))

    def test_request_budget_never_widened(self):
        self.assertEqual(a.job_payload(BODY, 30)['maximum_credits'], 20)
        self.assertEqual(a.job_payload(BODY, 5)['maximum_credits'], 5)
        for cap in [-1, True, 1.5]:
            with self.assertRaises(a.ClientError):
                a.job_payload(BODY, cap)

    def test_conflicting_options_and_oversize_rejected(self):
        with self.assertRaises(a.ClientError):
            a.job_payload(dict(BODY, input={'options': {}}, options={}))
        with self.assertRaises(a.ClientError):
            a.job_payload(dict(BODY, input={'text': 'x' * a.MAX_JSON}))

    def test_every_contract_operation_routes_correctly(self):
        for name, (method, path) in a.OPERATIONS.items():
            with self.subTest(name=name):
                t = Transport({})
                resource = 'ai_clipper' if '{tool}' in path else ID if '{id}' in path else None
                a.Client(key='test-key', opener=t).call(name, resource, idempotency='operation-test' if name in {'submit', 'export-clip'} else None)
                self.assertEqual(t.requests[0].method, method)
                self.assertEqual(t.requests[0].full_url, a.DEFAULT_BASE + path.replace('{id}', ID).replace('{tool}', 'ai_clipper'))

    def test_standalone_skill_install(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'reclip'
            shutil.copytree(SCRIPT.parents[1], target, ignore=shutil.ignore_patterns('__pycache__'))
            env = dict(os.environ)
            env.pop('RECLIP_API_KEY', None)
            result = subprocess.run([sys.executable, str(target / 'scripts/reclip_api.py'), 'tool', 'ai_clipper', '--offline'], cwd=folder, env=env, capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['snapshot']['id'], 'ai_clipper')


if __name__ == '__main__':
    unittest.main()
