import base64
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from privacy import plan_privacy, apply_changes, decrypt_payload
from catalog import read_catalog, render_directory, validate_choice
from server import Publisher, PublishError, run_command

ROOT=Path(__file__).resolve().parents[1]
PASSWORD='Album-fixture-passphrase-2026!'
NEW_PASSWORD='A-different-fixture-passphrase-2026!'


class PrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        shutil.copytree(ROOT/'content/photos',self.root/'content/photos')
        shutil.copyfile(ROOT/'photos.html',self.root/'photos.html')
        self.before={str(p.relative_to(self.root)).replace('\\','/'):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def tearDown(self): self.temp.cleanup()

    def lock(self):
        changes=plan_privacy(self.root,'companions','lock',PASSWORD)
        apply_changes(self.root,changes)
        return changes

    def test_plan_has_no_effect_until_applied_and_password_is_not_stored(self):
        changes=plan_privacy(self.root,'companions','lock',PASSWORD)
        self.assertEqual((self.root/'photos.html').read_bytes(),self.before['photos.html'])
        self.assertNotIn(PASSWORD.encode(),b''.join(data for data in changes.values() if data))
        self.assertIn('content/photos/private/companions.enc.json',changes)

    def test_locked_current_tree_has_no_clear_photos_or_noscript_bypass(self):
        self.lock()
        albums,photos=read_catalog(self.root)
        album=next(a for a in albums if a['id']=='companions')
        self.assertTrue(album['protected'])
        self.assertEqual(album['count'],2)
        self.assertFalse(any(p['category']=='companions' for p in photos))
        for name in ['friends-table-full.webp','friends-table-thumb.webp','friends-evening-full.webp','friends-evening-thumb.webp']:
            self.assertFalse((self.root/'content/photos/images'/name).exists())
        page=(self.root/'content/photos/companions.html').read_text(encoding='utf-8')
        self.assertIn('album-password-form',page)
        self.assertNotIn('friends-table',page)
        self.assertNotIn('friends-evening',page)
        directory=render_directory(albums,photos)
        self.assertIn('data-protected="true"',directory)
        self.assertIn('companions-locked.webp',directory)
        with self.assertRaises(ValueError): validate_choice(self.root,'companions','images/friends-table-full.webp')

    def test_wrong_password_and_tampering_do_not_modify_tree(self):
        self.lock()
        path=self.root/'content/photos/private/companions.enc.json'
        raw=path.read_bytes()
        with self.assertRaises(ValueError): plan_privacy(self.root,'companions','unlock','incorrect-password')
        self.assertEqual(path.read_bytes(),raw)
        data=json.loads(raw); encrypted=bytearray(base64.b64decode(data['ciphertext']));encrypted[12]^=1;data['ciphertext']=base64.b64encode(encrypted).decode()
        with self.assertRaises(ValueError): decrypt_payload(data,PASSWORD,'companions')
        with self.assertRaises(ValueError): decrypt_payload(json.loads(raw),PASSWORD,'harbin')

    def test_roundtrip_restores_source_files_and_other_albums_are_unchanged(self):
        self.lock()
        for name,data in self.before.items():
            if name.startswith('content/photos/images/') and 'friends-' not in name:
                self.assertEqual((self.root/name).read_bytes(),data)
        apply_changes(self.root,plan_privacy(self.root,'companions','unlock',PASSWORD))
        for name,data in self.before.items():
            if name.startswith('content/photos/images/') or name=='content/photos/companions.html':
                self.assertEqual((self.root/name).read_bytes(),data)
        self.assertFalse((self.root/'content/photos/private/companions.enc.json').exists())
        self.assertEqual(json.loads((self.root/'content/photos/index.json').read_text(encoding='utf-8')),json.loads(self.before['content/photos/index.json']))

    def test_password_rotation_only_new_password_decrypts(self):
        self.lock()
        apply_changes(self.root,plan_privacy(self.root,'companions','password',PASSWORD,NEW_PASSWORD))
        data=json.loads((self.root/'content/photos/private/companions.enc.json').read_text())
        with self.assertRaises(ValueError): decrypt_payload(data,PASSWORD,'companions')
        self.assertEqual(len(decrypt_payload(data,NEW_PASSWORD,'companions')['photos']),2)

    def test_multiple_albums_restore_in_catalog_and_original_internal_order(self):
        for album in ['harbin','companions','nenjiang']:
            apply_changes(self.root,plan_privacy(self.root,album,'lock',PASSWORD))
        for album in ['companions','harbin','nenjiang']:
            apply_changes(self.root,plan_privacy(self.root,album,'unlock',PASSWORD))
        photos=json.loads((self.root/'content/photos/index.json').read_text(encoding='utf-8'))
        self.assertEqual(photos,json.loads(self.before['content/photos/index.json']))

    def test_weak_password_or_unknown_album_is_rejected_without_changes(self):
        for album,password in [('companions','short'),('unknown',PASSWORD)]:
            with self.assertRaises(ValueError): plan_privacy(self.root,album,'lock',password)
        self.assertEqual((self.root/'photos.html').read_bytes(),self.before['photos.html'])

    def git(self,*args):
        return run_command(['git','-C',str(self.root),*args])

    def initialize_git(self):
        self.git('init','-b','main');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.test')
        self.git('add','.');self.git('commit','-m','Fixture baseline')
        self.git('remote','add','origin','https://github.com/ChenfoRest-LOVE/ChenfoRest-LOVE.github.io.git')
        self.git('update-ref','refs/remotes/origin/main',self.git('rev-parse','HEAD'))

    def test_failed_commit_restores_exact_files_and_clean_index(self):
        self.initialize_git()
        def runner(args,timeout=90):
            if args[0]!='git': self.fail('Unexpected non-Git publication command')
            if args[3] in ['fetch','push']: return ''
            if 'commit' in args: raise RuntimeError('Fixture commit failure')
            return run_command(args,timeout)
        with self.assertRaises(PublishError): Publisher(self.root,runner).publish_privacy('companions','lock',PASSWORD)
        self.assertEqual(self.git('status','--porcelain'),'')
        for name,data in self.before.items(): self.assertEqual((self.root/name).read_bytes(),data)

    def test_failed_push_can_retry_without_password_or_server_deploy(self):
        self.initialize_git(); fail=True
        def runner(args,timeout=90):
            nonlocal fail
            if args[0]!='git': self.fail('Unexpected server deploy')
            if args[3]=='fetch': return ''
            if args[3]=='push':
                if fail: fail=False;raise RuntimeError('Fixture transport failure')
                return ''
            return run_command(args,timeout)
        publisher=Publisher(self.root,runner)
        with self.assertRaises(PublishError) as caught: publisher.publish_privacy('companions','lock',PASSWORD)
        self.assertEqual(caught.exception.step,'push')
        self.assertEqual(self.git('status','--porcelain'),'')
        revision=self.git('rev-parse','HEAD')
        self.assertEqual(publisher.publish_pending()['revision'],revision)
        self.assertEqual(self.git('log','-1','--format=%s'),'Set album privacy: companions')
        self.assertNotIn(PASSWORD,self.git('show','--format=full','HEAD'))

    def test_write_failure_rolls_back_before_publishing(self):
        import privacy
        original=privacy.atomic_bytes; failed=False
        def once(path,data):
            nonlocal failed
            if path.name.endswith('.enc.json') and not failed:
                failed=True;raise OSError('Fixture disk failure')
            original(path,data)
        with patch('privacy.atomic_bytes',side_effect=once):
            with self.assertRaises(OSError): self.lock()
        for name,data in self.before.items(): self.assertEqual((self.root/name).read_bytes(),data)


if __name__=='__main__': unittest.main()
