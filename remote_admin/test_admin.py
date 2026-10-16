import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest

from server import Store, AdminServer, SetupServer, PasswordError, RateLimited
import time
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='Fixture-only-passphrase-2026!'


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'admin.sqlite'
        self.store=Store(self.path)

    def tearDown(self):
        self.temp.cleanup()

    def test_single_admin_and_no_plaintext_password_or_session(self):
        self.store.setup('admin',PASSWORD)
        with self.assertRaises(PasswordError): self.store.setup('other',PASSWORD)
        token=self.store.login('admin',PASSWORD,'test')
        self.assertTrue(self.store.session_valid(token))
        self.assertNotIn(PASSWORD.encode(),self.path.read_bytes())
        self.assertNotIn(token.encode(),self.path.read_bytes())
        self.store.logout(token)
        self.assertFalse(self.store.session_valid(token))

    def test_strong_password_required_and_wrong_password_rate_limited(self):
        with self.assertRaises(PasswordError): self.store.setup('admin','short')
        self.store.setup('admin',PASSWORD)
        for _ in range(5):
            with self.assertRaises(PasswordError): self.store.login('admin','wrong','same-ip')
        with self.assertRaises(RateLimited): self.store.login('admin',PASSWORD,'same-ip')

    def test_cover_persistence_survives_store_restart(self):
        self.store.set_cover('companions','images/friends-table-full.webp')
        self.assertEqual(Store(self.path).covers()['companions'],'images/friends-table-full.webp')

    def test_expired_session_and_restart_persistent_login_limit(self):
        self.store.setup('admin',PASSWORD)
        token=self.store.login('admin',PASSWORD,'test')
        with self.store.db() as db:
            db.execute('UPDATE sessions SET expires=?',(time.time()-1,))
        self.assertFalse(self.store.session_valid(token))
        for _ in range(5):
            with self.assertRaises(PasswordError): self.store.login('admin','wrong','test')
        with self.assertRaises(RateLimited): Store(self.path).login('admin',PASSWORD,'test')

    def test_concurrent_bootstrap_only_creates_one_admin(self):
        def setup(name):
            try: self.store.setup(name,PASSWORD); return True
            except (PasswordError,RateLimited): return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(setup,['first','second'])),1)
        with self.store.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM admin').fetchone()[0],1)


class HttpTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'db.sqlite')
        self.store.setup('admin',PASSWORD)
        self.server=AdminServer(('127.0.0.1',0),self.store,ROOT,'https://denss.asia')
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(); self.temp.cleanup()

    def request(self,method,path,data=None,headers=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.server.server_port)
        conn.request(method,path,body=json.dumps(data).encode() if data is not None else None,headers={'Host':'denss.asia',**(headers or {})})
        response=conn.getresponse(); raw=response.read()
        result=(response.status,dict(response.getheaders()),json.loads(raw) if response.getheader('Content-Type','').startswith('application/json') else raw)
        conn.close(); return result

    def login(self):
        status,headers,body=self.request('POST','/api/admin/login',{'username':'admin','password':PASSWORD},{'Origin':'https://denss.asia','Content-Type':'application/json'})
        self.assertEqual(status,200)
        return headers['Set-Cookie'].split(';',1)[0],body['csrf'],headers

    def test_login_cookie_and_no_public_signup(self):
        _,_,headers=self.login()
        self.assertIn('HttpOnly',headers['Set-Cookie']); self.assertIn('Secure',headers['Set-Cookie']); self.assertIn('SameSite=Strict',headers['Set-Cookie'])
        self.assertEqual(self.request('POST','/api/admin/setup',{}, {'Origin':'https://denss.asia','Content-Type':'application/json'})[0],404)
        self.assertEqual(self.request('GET','/api/admin/state')[0],401)

    def test_authenticated_cover_change_and_cross_album_rejection(self):
        cookie,csrf,_=self.login()
        headers={'Cookie':cookie,'Origin':'https://denss.asia','Content-Type':'application/json','X-CSRF-Token':csrf}
        self.assertEqual(self.request('POST','/api/admin/cover',{'album':'harbin','file':'images/friends-table-full.webp'},headers)[0],422)
        self.assertEqual(self.request('POST','/api/admin/cover',{'album':'companions','file':'images/friends-table-full.webp'},headers)[0],200)
        self.assertEqual(self.request('GET','/api/covers')[2]['covers']['companions'],'images/friends-table-full.webp')

    def test_csrf_and_origin_required_and_logout_revokes_session(self):
        cookie,csrf,_=self.login()
        headers={'Cookie':cookie,'Origin':'https://denss.asia','Content-Type':'application/json','X-CSRF-Token':csrf}
        data={'album':'companions','file':'images/friends-table-full.webp'}
        for bad in [{**headers,'Origin':'https://evil.example'},{**headers,'X-CSRF-Token':'wrong'},{**headers,'Cookie':'wrong'}]:
            self.assertIn(self.request('POST','/api/admin/cover',data,bad)[0],[401,403])
        self.assertEqual(self.request('POST','/api/admin/logout',{},headers)[0],200)
        self.assertEqual(self.request('GET','/api/admin/state',headers={'Cookie':cookie})[0],401)

    def test_only_public_read_api_has_github_pages_cors(self):
        _,headers,_=self.request('GET','/api/covers',headers={'Origin':'https://chenforest-love.github.io'})
        self.assertEqual(headers.get('Access-Control-Allow-Origin'),'https://chenforest-love.github.io')
        self.assertNotIn('Access-Control-Allow-Credentials',headers)
        _,private_headers,_=self.request('GET','/api/admin/state',headers={'Origin':'https://chenforest-love.github.io'})
        self.assertNotIn('Access-Control-Allow-Origin',private_headers)
        _,evil_headers,_=self.request('GET','/api/covers',headers={'Origin':'https://evil.example'})
        self.assertNotIn('Access-Control-Allow-Origin',evil_headers)

    def test_host_request_format_and_asset_allowlist(self):
        self.assertEqual(self.request('GET','/admin/',headers={'Host':'evil.example'})[0],403)
        self.assertEqual(self.request('GET','/api/admin/assets/server.py')[0],404)
        self.assertEqual(self.request('GET','/admin/../../server.py')[0],404)
        self.assertEqual(self.request('POST','/api/admin/login',{}, {'Origin':'https://denss.asia','Content-Type':'text/plain'})[0],422)
        cookie,csrf,_=self.login()
        self.assertEqual(self.request('POST','/api/admin/cover',{}, {'Cookie':cookie,'Origin':'https://denss.asia','Content-Type':'application/json','X-CSRF-Token':'é'})[0],403)

    def test_catalog_filters_stale_overrides(self):
        self.store.set_cover('companions','images/removed-photo-full.webp')
        defaults=json.loads((ROOT/'content/photos/albums.json').read_text(encoding='utf-8'))
        expected=next(a['cover'] for a in defaults if a['id']=='companions')
        self.assertEqual(self.request('GET','/api/covers')[2]['covers']['companions'],expected)


class SetupTests(unittest.TestCase):
    def test_setup_is_local_only_and_once(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'db.sqlite')
            with self.assertRaises(ValueError): SetupServer(('0.0.0.0',0),store)
            server=SetupServer(('127.0.0.1',0),store)
            thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
            def request(method,path,data=None,headers=None):
                conn=http.client.HTTPConnection('127.0.0.1',server.server_port)
                conn.request(method,path,json.dumps(data).encode() if data else None,headers or {})
                result=conn.getresponse(); body=result.read(); output=(result.status,dict(result.getheaders()),body);conn.close();return output
            try:
                status,headers,_=request('GET','/')
                self.assertEqual(status,200)
                cookie=headers['Set-Cookie'].split(';',1)[0]
                host='http://127.0.0.1:'+str(server.server_port)
                _,_,body=request('GET','/state',headers={'Cookie':cookie,'Origin':host})
                csrf=json.loads(body)['csrf']
                auth={'Cookie':cookie,'Origin':host,'Content-Type':'application/json','X-CSRF-Token':csrf}
                data={'username':'admin','password':PASSWORD,'confirm':PASSWORD}
                self.assertEqual(request('POST','/setup',data,{**auth,'Origin':'https://evil.example'})[0],403)
                self.assertEqual(request('POST','/setup',data,auth)[0],200)
                self.assertEqual(request('GET','/')[0],410)
                self.assertEqual(request('POST','/setup',data,auth)[0],410)
            finally:
                server.shutdown();server.server_close();thread.join()


if __name__=='__main__': unittest.main()
