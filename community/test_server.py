import http.client
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
PASSWORD = 'Reader-http-fixture-2026!'


class HTTPTests(unittest.TestCase):
    def setUp(self):
        module_path = Path(__file__).with_name('server.py')
        self.assertTrue(module_path.exists(), 'Comments HTTP server is not implemented')
        spec = importlib.util.spec_from_file_location('community_http_test', module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.module = module
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        store = module.Store(Path(self.temp.name) / 'readers.sqlite', {'chire', 'yuemeng'})
        self.server = module.CommunityServer(('127.0.0.1', 0), store, ROOT)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.cookie, self.csrf = '', ''

    def request(self, path, data=None, headers=None, raw=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=15)
        request_headers = {'Cookie': self.cookie}
        method = 'GET'
        if data is not None or raw is not None:
            method = 'POST'
            request_headers.update({'Origin': self.server.origin, 'Content-Type': 'application/json', 'X-CSRF-Token': self.csrf})
        request_headers.update(headers or {})
        connection.request(method, path, raw if raw is not None else json.dumps(data) if data is not None else None, request_headers)
        response = connection.getresponse()
        body = response.read()
        result = response.status, dict(response.getheaders()), body
        connection.close()
        return result

    def register(self):
        status, headers, raw = self.request('/api/community/register', {'username': 'forest', 'password': PASSWORD})
        self.assertEqual(201, status, raw)
        self.cookie = headers['Set-Cookie'].split(';')[0]
        self.csrf = json.loads(raw)['csrf']
        return headers

    def test_complete_session_comment_logout_chain(self):
        headers = self.register()
        self.assertIn('HttpOnly', headers['Set-Cookie'])
        self.assertIn('SameSite=Strict', headers['Set-Cookie'])
        self.assertNotIn('Secure', headers['Set-Cookie'])
        status, _, raw = self.request('/api/community/session')
        self.assertEqual('forest', json.loads(raw)['user']['username'])
        status, _, raw = self.request('/api/community/comments', {'article': 'chire', 'text': '🌒' * 100})
        self.assertEqual(201, status, raw)
        item = json.loads(raw)
        self.assertEqual(100, len(item['text']))
        status, _, raw = self.request('/api/community/comments?article=chire')
        self.assertEqual(item['id'], json.loads(raw)['comments'][0]['id'])
        status, _, raw = self.request('/api/community/comments?article=yuemeng')
        self.assertEqual([], json.loads(raw)['comments'])
        self.assertEqual(200, self.request(f"/api/community/comments/{item['id']}/delete", {})[0])
        self.assertEqual(200, self.request('/api/community/logout', {})[0])
        self.assertIsNone(json.loads(self.request('/api/community/session')[2])['user'])
        self.assertEqual(401, self.request('/api/community/comments', {'article': 'chire', 'text': 'x'})[0])
        self.assertEqual(200, self.request('/api/community/login', {'username': 'forest', 'password': PASSWORD})[0])

    def test_origin_host_json_csrf_and_invalid_lengths(self):
        self.assertEqual(403, self.request('/api/community/session', headers={'Host': 'attacker.example'})[0])
        credentials = {'username': 'forest', 'password': PASSWORD}
        self.assertEqual(403, self.request('/api/community/register', credentials, {'Origin': 'https://attacker.example'})[0])
        self.assertEqual(403, self.request('/api/community/register', credentials, {'Sec-Fetch-Site': 'cross-site'})[0])
        self.assertEqual(415, self.request('/api/community/register', credentials, {'Content-Type': 'text/plain'})[0])
        self.assertEqual(413, self.request('/api/community/register', raw='x' * 5000)[0])
        self.assertEqual(422, self.request('/api/community/register', raw='[]')[0])
        self.assertEqual(422, self.request('/api/community/register', raw='{invalid')[0])
        self.register()
        self.assertEqual(403, self.request('/api/community/logout', {}, {'X-CSRF-Token': ''})[0])
        for text in ['字' * 101, '🌒' * 101, '', []]:
            self.assertEqual(422, self.request('/api/community/comments', {'article': 'chire', 'text': text})[0])
        self.assertEqual(404, self.request('/api/community/comments?article=invalid')[0])
        self.assertEqual(422, self.request('/api/community/comments?article=chire&before=NaN')[0])

    def test_only_public_files_and_no_api_caching_or_cors(self):
        for path in ['/', '/content/writing/chire.html', '/assets/comments-config.js', '/content/photos/albums.json']:
            status, _, raw = self.request(path)
            self.assertEqual(200, status, path)
            if path.endswith('config.js'):
                self.assertIn(b'enabled: true', raw)
            if path.endswith('.json'):
                self.assertTrue(json.loads(raw))
        for path in ['/community/store.py', '/manage/server.py', '/remote_admin/server.py', '/.git/config', '/assets/../../community/store.py', '/content/%2e%2e/%2e%2e/community/store.py', '/content/photos/', '/assets/../theme.css']:
            self.assertIn(self.request(path)[0], [403, 404], path)
        status, headers, _ = self.request('/api/community/session', headers={'Origin': 'https://elsewhere.example'})
        self.assertEqual(200, status)
        self.assertEqual('no-store', headers['Cache-Control'])
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_production_requires_https_and_secure_separate_cookie(self):
        cls = self.module.CommunityServer
        for origin in ['http://example.com', 'https://example.com/path', 'https://user@example.com', 'https://example.com?x=1']:
            with self.assertRaises(ValueError):
                cls(('127.0.0.1', 0), self.server.store, ROOT, origin=origin)
        with self.assertRaises(ValueError):
            cls(('0.0.0.0', 0), self.server.store, ROOT)
        server = cls(('127.0.0.1', 0), self.server.store, ROOT, origin='https://example.com', trust_proxy=True)
        self.addCleanup(server.server_close)
        self.assertTrue(server.secure)
        self.assertEqual('__Host-forest_reader', server.cookie_name)

    def test_rejected_post_body_in_later_packet_keeps_error_readable(self):
        for origin, mime, payload, expected in [
                ('https://attacker.example', 'application/json', b'{"username":"reader"}', 403),
                (self.server.origin, 'text/plain', b'{"username":"reader"}', 415),
                (self.server.origin, 'application/json', b'x' * 5000, 413)]:
            connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
            connection.putrequest('POST', '/api/community/register')
            connection.putheader('Origin', origin)
            connection.putheader('Content-Type', mime)
            connection.putheader('Content-Length', str(len(payload)))
            connection.endheaders()
            time.sleep(.05)
            connection.send(payload)
            response = connection.getresponse()
            self.assertEqual(expected, response.status)
            self.assertIn('error', json.loads(response.read()))
            connection.close()


if __name__ == '__main__':
    unittest.main()
