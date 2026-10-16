import http.client
import json
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
import subprocess
from unittest.mock import Mock

from catalog import set_cover
from server import ManagerServer, Publisher, PublishError, run_command

SOURCE = Path(__file__).resolve().parents[1]


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'content/photos').mkdir(parents=True)
        for name in ['index.json', 'albums.json']:
            shutil.copyfile(SOURCE / 'content/photos' / name, self.root / 'content/photos' / name)
        shutil.copyfile(SOURCE / 'photos.html', self.root / 'photos.html')

    def tearDown(self):
        self.temp.cleanup()


class CatalogTests(Fixture):
    def test_cover_is_persisted_in_config_and_public_html(self):
        self.assertTrue(set_cover(self.root, 'companions', 'images/friends-table-full.webp'))
        albums = json.loads((self.root / 'content/photos/albums.json').read_text(encoding='utf-8'))
        self.assertEqual(next(a['cover'] for a in albums if a['id'] == 'companions'), 'images/friends-table-full.webp')
        html = (self.root / 'photos.html').read_text(encoding='utf-8')
        self.assertIn('content/photos/images/friends-table-thumb.webp', html)
        self.assertIn('返回首页', html)
        self.assertIn('哈尔滨', html)
        self.assertFalse(set_cover(self.root, 'companions', 'images/friends-table-full.webp'))

    def test_cross_album_and_unknown_paths_cannot_change_any_files(self):
        before = [(p, p.read_bytes()) for p in [self.root / 'photos.html', self.root / 'content/photos/albums.json']]
        for album, file in [('harbin', 'images/friends-table-full.webp'), ('companions', '../../.git/config'), ('unknown', 'images/friends-table-full.webp')]:
            with self.assertRaises(ValueError):
                set_cover(self.root, album, file)
        for path, data in before:
            self.assertEqual(path.read_bytes(), data)


class PublisherTests(Fixture):
    def runner(self, dirty=False, branch='main', failure=None):
        self.commands = []
        def run(args, timeout=90):
            self.commands.append(args)
            tail = args[3:] if args[0] == 'git' else args
            if failure and failure in tail:
                raise RuntimeError('simulated transport failure')
            if tail[:2] == ['branch', '--show-current']:
                return branch
            if tail[:2] == ['status', '--porcelain']:
                return ' M writing.html' if dirty else ''
            if tail[:3] == ['remote', 'get-url', 'origin']:
                return 'https://github.com/ChenfoRest-LOVE/ChenfoRest-LOVE.github.io.git'
            if tail[:2] == ['rev-list', 'origin/main..HEAD']:
                return ''
            if tail[:2] == ['log', '-1']:
                return 'Forest' if '%an' in tail[-1] else 'author@example.test'
            if tail[:2] == ['rev-parse', 'HEAD']:
                return 'a' * 40
            return ''
        return run

    def test_dirty_or_non_main_work_is_not_published(self):
        for dirty, branch in [(True, 'main'), (False, 'feature')]:
            with self.assertRaises(PublishError):
                Publisher(self.root, runner=self.runner(dirty, branch)).publish('companions', 'images/friends-table-full.webp')
            self.assertFalse(any('push' in cmd for cmd in self.commands))

    def test_publish_stages_only_cover_files_and_uses_existing_deploy_script(self):
        result = Publisher(self.root, runner=self.runner()).publish('companions', 'images/friends-table-full.webp')
        self.assertEqual(result['revision'], 'a' * 40)
        add = next(c for c in self.commands if 'add' in c)
        self.assertEqual(add[3:], ['add', '--', 'content/photos/albums.json', 'photos.html'])
        self.assertTrue(any(c[-3:] == ['push', 'origin', 'main'] for c in self.commands))
        self.assertTrue(any(str(self.root / 'deploy/publish.ps1') in c for c in self.commands))
        deployment = next(c for c in self.commands if str(self.root / 'deploy/publish.ps1') in c)
        self.assertEqual(deployment[-2:], ['-Revision', 'a' * 40])
        commit = next(c for c in self.commands if 'commit' in c)
        self.assertIn('--only', commit)
        self.assertEqual(commit[-3:], ['--', 'content/photos/albums.json', 'photos.html'])

    def test_failed_commit_restores_files_and_can_be_retried(self):
        originals = {name:(self.root/name).read_bytes() for name in ['photos.html','content/photos/albums.json']}
        with self.assertRaises(PublishError) as error:
            Publisher(self.root, runner=self.runner(failure='commit')).publish('companions', 'images/friends-table-full.webp')
        self.assertEqual(error.exception.step, 'save')
        for name, content in originals.items():
            self.assertEqual((self.root/name).read_bytes(), content)
        self.assertTrue(any('restore' in c and '--staged' in c for c in self.commands))
        self.assertEqual(Publisher(self.root, runner=self.runner()).publish('companions', 'images/friends-table-full.webp')['revision'], 'a'*40)

    def test_failed_push_does_not_claim_server_was_synced(self):
        with self.assertRaises(PublishError) as error:
            Publisher(self.root, runner=self.runner(failure='push')).publish('companions', 'images/friends-table-full.webp')
        self.assertEqual(error.exception.step, 'push')
        self.assertFalse(any(str(self.root / 'deploy/publish.ps1') in c for c in self.commands))


class AccessTests(Fixture):
    def setUp(self):
        super().setUp()
        self.publisher = Mock()
        self.publisher.publish.return_value = {'revision': 'a' * 40}
        self.server = ManagerServer(('127.0.0.1', 0), self.root, self.publisher)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = 'http://127.0.0.1:' + str(self.server.server_port)
        status, headers, body = self.request('GET', '/photos.html')
        self.cookie = headers['Set-Cookie'].split(';', 1)[0]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port)
        conn.request(method, path, body=json.dumps(data).encode() if data is not None else None, headers=headers or {})
        result = conn.getresponse()
        body = result.read()
        status, response_headers = result.status, dict(result.getheaders())
        conn.close()
        return status, response_headers, body

    def auth(self):
        return {'Cookie': self.cookie, 'Origin': self.origin, 'Content-Type': 'application/json', 'X-CSRF-Token': self.server.csrf}

    def test_only_public_assets_are_readable_and_management_injection_is_local(self):
        status, _, body = self.request('GET', '/photos.html')
        self.assertEqual(status, 200)
        self.assertIn(b'/_manage/controls.js', body)
        for path in ['/.git/config', '/manage/server.py', '/content/%2e%2e/photos.html']:
            self.assertEqual(self.request('GET', path)[0], 404)
        self.assertEqual(self.request('GET', '/photos.html', headers={'Host': 'evil.example'})[0], 403)

    def test_missing_session_csrf_or_cross_origin_cannot_publish(self):
        data = {'album': 'companions', 'file': 'images/friends-table-full.webp'}
        for headers in [{}, {**self.auth(), 'Origin': 'https://evil.example'}, {**self.auth(), 'X-CSRF-Token': 'wrong'}, {**self.auth(), 'Cookie': 'wrong'}]:
            self.assertEqual(self.request('POST', '/_manage/cover', data, headers)[0], 403)
        self.publisher.publish.assert_not_called()

    def test_valid_request_publishes_and_invalid_choice_does_not(self):
        self.assertEqual(self.request('POST', '/_manage/cover', {'album': 'harbin', 'file': 'images/friends-table-full.webp'}, self.auth())[0], 422)
        status, _, body = self.request('POST', '/_manage/cover', {'album': 'companions', 'file': 'images/friends-table-full.webp'}, self.auth())
        self.assertEqual(status, 200)
        self.publisher.publish.assert_called_once_with('companions', 'images/friends-table-full.webp')

    def test_concurrent_publish_is_rejected(self):
        self.server.publish_lock.acquire()
        try:
            self.assertEqual(self.request('POST', '/_manage/cover', {'album':'companions', 'file':'images/friends-table-full.webp'}, self.auth())[0], 409)
        finally:
            self.server.publish_lock.release()

    def test_cannot_bind_to_public_interface(self):
        with self.assertRaises(ValueError):
            ManagerServer(('0.0.0.0', 0), self.root, self.publisher)


class GitIntegrationTests(Fixture):
    def test_real_commit_failure_restores_clean_tree_then_retry_succeeds(self):
        def git(*args):
            return run_command(['git','-C',str(self.root),*args])
        git('init','-b','main')
        git('config','user.name','Fixture')
        git('config','user.email','fixture@example.test')
        git('add','.')
        git('commit','-m','Fixture baseline')
        git('remote','add','origin','https://github.com/ChenfoRest-LOVE/ChenfoRest-LOVE.github.io.git')
        git('update-ref','refs/remotes/origin/main',git('rev-parse','HEAD'))
        fail = True
        def runner(args,timeout=90):
            nonlocal fail
            if args[0] != 'git' or args[3] in ['fetch','push']:
                return ''  # No network or actual deployment in this integration test.
            if 'commit' in args and fail:
                fail = False
                raise RuntimeError('Injected commit failure')
            return run_command(args,timeout)
        publisher = Publisher(self.root,runner=runner)
        with self.assertRaises(PublishError):
            publisher.publish('companions','images/friends-table-full.webp')
        self.assertEqual(git('status','--porcelain'), '')
        result = publisher.publish('companions','images/friends-table-full.webp')
        self.assertEqual(result['revision'],git('rev-parse','HEAD'))
        self.assertEqual(set(git('diff-tree','--no-commit-id','--name-only','-r','HEAD').splitlines()), {'photos.html','content/photos/albums.json'})
        self.assertEqual(git('status','--porcelain'), '')

    @unittest.skipUnless(shutil.which('pwsh'), 'PowerShell 7 not available')
    def test_powershell_rejects_changed_revision_before_any_ssh_call(self):
        script = str(SOURCE/'deploy/publish.ps1').replace("'","''")
        command = "function git { if ($args -contains 'rev-parse') { '" + 'a'*40 + "' }; $global:LASTEXITCODE=0 }; function ssh { throw 'UNEXPECTED_SSH' }; function scp { throw 'UNEXPECTED_SCP' }; & '" + script + "' -Revision '" + 'b'*40 + "'"
        result = subprocess.run([shutil.which('pwsh'),'-NoProfile','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
        self.assertNotEqual(result.returncode,0)
        self.assertIn('origin/main changed',result.stderr)
        self.assertNotIn('UNEXPECTED_SSH',result.stderr)
        self.assertNotIn('UNEXPECTED_SCP',result.stderr)


if __name__ == '__main__':
    unittest.main()
