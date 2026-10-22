import hashlib
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest

MODULE = Path(__file__).with_name('store.py')
PASSWORD = 'Reader-fixture-password-2026!'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(MODULE.exists(), 'Reader accounts and comments store is not implemented')
        spec = importlib.util.spec_from_file_location('community_store_test', MODULE)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'readers.sqlite'
        self.store = self.module.Store(self.path, {'chire', 'yuemeng'})

    def reader(self, name='forest', ip='one'):
        token = self.store.register(name, PASSWORD, ip)
        return token, self.store.session(token)

    def rejects(self, status, action):
        with self.assertRaises(self.module.Problem) as caught:
            action()
        self.assertEqual(status, caught.exception.status)

    def test_password_and_session_hashes_logout_and_persistence(self):
        token, user = self.reader()
        self.assertEqual('forest', user['username'])
        raw = self.path.read_bytes()
        self.assertNotIn(PASSWORD.encode(), raw)
        self.assertNotIn(token.encode(), raw)
        other = self.module.Store(self.path, {'chire', 'yuemeng'})
        self.assertEqual(user, other.session(token))
        other.logout(token)
        self.assertIsNone(self.store.session(token))
        token = self.store.login('FoReSt', PASSWORD, 'two')
        self.assertEqual(user, self.store.session(token))
        with self.store.db() as db:
            db.execute('UPDATE sessions SET expires=0')
        self.assertIsNone(self.store.session(token))
        self.assertIsNone(self.store.session('invalid'))

    def test_credentials_and_case_insensitive_unique_username(self):
        self.reader()
        self.rejects(409, lambda: self.reader('FOREST', 'two'))
        for name, password in [('a', PASSWORD), ('汉字用户', PASSWORD), ('okay', 'short'), ('okay', 123)]:
            self.rejects(422, lambda: self.store.register(name, password, 'invalid'))
        self.rejects(401, lambda: self.store.login('forest', 'wrong', 'two'))
        self.rejects(401, lambda: self.store.login('absent', PASSWORD, 'two'))

    def test_100_codepoints_and_article_separation_persist(self):
        _, user = self.reader()
        item = self.store.post('chire', '  ' + '文' * 99 + '🌒' + '  ', user, 'one')
        self.assertEqual(100, len(item['text']))
        self.assertEqual([], self.store.list('yuemeng', user)['comments'])
        reopened = self.module.Store(self.path, {'chire', 'yuemeng'})
        self.assertEqual(item['text'], reopened.list('chire', None)['comments'][0]['text'])
        self.assertFalse(reopened.list('chire', None)['comments'][0]['mine'])
        self.assertTrue(reopened.list('chire', user)['comments'][0]['mine'])

    def test_validation_before_write_and_plain_text_preserved(self):
        _, user = self.reader()
        for text in ['', ' \n\t ', '字' * 101, '🌒' * 101, None, [], '\x00bad', '\ud800']:
            self.rejects(422, lambda: self.store.post('chire', text, user, 'one'))
        self.rejects(404, lambda: self.store.post('missing', 'test', user, 'one'))
        self.rejects(401, lambda: self.store.post('chire', 'test', None, 'one'))
        item = self.store.post('chire', '<img src=x onerror=alert(1)>', user, 'one')
        self.assertEqual('<img src=x onerror=alert(1)>', item['text'])

    def test_only_author_can_delete(self):
        _, first = self.reader()
        _, second = self.reader('another', 'two')
        item = self.store.post('chire', 'A comment', first, 'one')
        self.rejects(403, lambda: self.store.delete(item['id'], second))
        self.rejects(401, lambda: self.store.delete(item['id'], None))
        self.assertEqual(1, len(self.store.list('chire', second)['comments']))
        self.store.delete(item['id'], first)
        self.assertEqual([], self.store.list('chire', first)['comments'])
        self.rejects(404, lambda: self.store.delete(item['id'], first))

    def test_pagination_and_invalid_cursor(self):
        _, user = self.reader()
        with self.store.db() as db:
            for n in range(25):
                db.execute('INSERT INTO comments(article,user_id,text,created) VALUES (?,?,?,?)', ('chire', user['id'], str(n), time.time()))
        first = self.store.list('chire', user)
        self.assertEqual(20, len(first['comments']))
        second = self.store.list('chire', user, first['next'])
        self.assertEqual(5, len(second['comments']))
        self.assertIsNone(second['next'])
        self.assertFalse({x['id'] for x in first['comments']} & {x['id'] for x in second['comments']})
        self.rejects(422, lambda: self.store.list('chire', user, -1))
        self.rejects(422, lambda: self.store.list('chire', user, 2**64))

    def test_persistent_rate_limits_and_normalization(self):
        _, user = self.reader()
        self.store.post('chire', ' e\u0301 ', user, 'one')
        self.assertEqual('é', self.store.list('chire', user)['comments'][0]['text'])
        reopened = self.module.Store(self.path, {'chire', 'yuemeng'})
        self.rejects(429, lambda: reopened.post('yuemeng', 'again', user, 'two'))
        self.assertEqual([], reopened.list('yuemeng', user)['comments'])
        for _ in range(10):
            self.rejects(401, lambda: self.store.login('forest', 'bad', 'bad-ip'))
        self.rejects(429, lambda: reopened.login('forest', PASSWORD, 'bad-ip'))
        for _ in range(5):
            self.rejects(409, lambda: self.reader('forest', 'register-ip'))
        self.rejects(429, lambda: reopened.register('new-reader', PASSWORD, 'register-ip'))

    def test_invisible_boundary_whitespace_uses_python_strip_rules(self):
        _, user = self.reader()
        self.rejects(422, lambda: self.store.post('chire', '\ufeff' + '字' * 100, user, 'one'))
        item = self.store.post('chire', '\u0085' + '字' * 100 + '\u0085', user, 'one')
        self.assertEqual(100, len(item['text']))


if __name__ == '__main__':
    unittest.main()
