import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
import zipfile
from unittest import mock

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import release_metadata as metadata
import publish_release
import source_policy
import clean_source_checkout
import package_release
import subprocess
import contextlib
import io

class ReleaseMetadataTests(unittest.TestCase):
    def test_archive_root_allowlist_rejects_each_old_guide_and_unreviewed_new_file(self):
        for name in [*source_policy.MOVED_DOCUMENTS,'UNREVIEWED.md']:
            with self.subTest(name=name),io.BytesIO() as content:
                with zipfile.ZipFile(content,'w') as archive:archive.writestr('vita-audio-receiver/'+name,'stale')
                with zipfile.ZipFile(content) as archive,self.assertRaisesRegex(ValueError,'Unapproved'):source_policy.check_archive(archive)
        with io.BytesIO() as content:
            with zipfile.ZipFile(content,'w') as archive:
                archive.writestr('vita-audio-receiver/README.md','current')
                archive.writestr('vita-audio-receiver/docs/dev/BUILDING.md','current')
            with zipfile.ZipFile(content) as archive:source_policy.check_archive(archive)

    def test_obsolete_or_unapproved_root_docs_cannot_replace_an_existing_archive(self):
        output=self.root.parent/(self.root.name+'.zip');self.addCleanup(lambda:output.unlink(missing_ok=True))
        output.write_bytes(b'previous')
        for name in [*source_policy.MOVED_DOCUMENTS,'UNREVIEWED.md']:
            p=self.root/name;p.write_text('stale')
            with self.subTest(name=name),self.assertRaises(ValueError):package_release.package(self.root,output)
            self.assertEqual(output.read_bytes(),b'previous');p.unlink()

    def test_git_cleanup_records_all_ten_deletions_and_untracks_generated_files(self):
        for old,new in source_policy.MOVED_DOCUMENTS.items():
            (self.root/old).write_text('old');p=self.root/new;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('replacement')
        for name in source_policy.GENERATED_NATIVE:
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('generated')
        (self.root/'keep.txt').write_text('keep')
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        def git(*args):return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True,text=True)
        git('add','.');git('-c','user.name=Fixture','-c','user.email=fixture@example.invalid','commit','-qm','Fixture')
        with self.assertRaisesRegex(ValueError,'Obsolete'):source_policy.check_checkout(self.root,True)
        with contextlib.redirect_stdout(io.StringIO()):
            clean_source_checkout.clean(self.root,False)
            self.assertTrue((self.root/'BUILDING.md').exists())
            clean_source_checkout.clean(self.root,True)
            clean_source_checkout.clean(self.root,True) # repeat safely
        source_policy.check_checkout(self.root,True)
        tracked=set(git('ls-files').stdout.splitlines())
        self.assertFalse(tracked&set(source_policy.MOVED_DOCUMENTS));self.assertFalse(tracked&source_policy.GENERATED_NATIVE)
        self.assertTrue(all((self.root/name).exists() for name in source_policy.GENERATED_NATIVE))
        self.assertEqual((self.root/'keep.txt').read_text(),'keep')

    def test_git_policy_also_rejects_generated_binaries_without_stale_guides(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        (self.root/'pc/native/opus.dll').write_bytes(b'generated')
        subprocess.run(['git','-C',str(self.root),'add','.'],check=True)
        with self.assertRaisesRegex(ValueError,'must not be tracked'):source_policy.check_checkout(self.root,True)

    def test_cleanup_never_deletes_a_guide_without_its_replacement(self):
        subprocess.run(['git','init','-q',str(self.root)],check=True)
        old=self.root/'BUILDING.md';old.write_text('keep until replacement exists')
        with self.assertRaisesRegex(ValueError,'Missing replacement'):clean_source_checkout.clean(self.root,True)
        self.assertTrue(old.exists())
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        (self.root/'pc/native').mkdir(parents=True);(self.root/'pc/version.py').write_text("VERSION='1.3.1'\n")
        self.commit='a'*40

    def pe(self,name):
        raw=bytearray(80);raw[:2]=b'MZ';struct.pack_into('<I',raw,60,64);raw[64:70]=b'PE\0\0\x64\x86'
        (self.root/'pc/native'/name).write_bytes(raw)

    def assets(self):
        self.root.joinpath('RELEASE_NOTES.md').write_text('Public notes')
        out=self.root/'release';out.mkdir()
        for name in ('vita-audio-receiver-1.3.1.zip','vita-audio-receiver.vpk'):(out/name).write_bytes(name.encode())
        (out/'SHA256SUMS.txt').write_text(''.join(hashlib.sha256((out/n).read_bytes()).hexdigest()+'  '+n+'\n' for n in ('vita-audio-receiver-1.3.1.zip','vita-audio-receiver.vpk')))
        (out/'BUILD_INFO.txt').write_text('version=1.3.1\nsource_commit='+self.commit+'\n')
        return out

    def runner(self,draft=None,remote=None):
        def invoke(args,**kwargs):
            if args[1]=='api':return types.SimpleNamespace(returncode=0,stdout=(remote or self.commit)+'\n')
            if args[1:3]==['release','view']:return types.SimpleNamespace(returncode=1 if draft is None else 0,stdout=json.dumps({'isDraft':draft}))
            return types.SimpleNamespace(returncode=0)
        return mock.Mock(side_effect=invoke)

    def test_versions_tags_and_source_identity_are_validated(self):
        self.assertEqual(metadata.version(self.root),'1.3.1');metadata.check_ref(self.root,'refs/heads/main');metadata.check_ref(self.root,'refs/tags/v1.3.1')
        with self.assertRaises(ValueError):metadata.check_ref(self.root,'refs/tags/v1.3')
        with self.assertRaises(ValueError):metadata.source_commit('not-a-commit')
        (self.root/'src').mkdir();(self.root/'src/version.h').write_text('#define RECEIVER_VERSION "1.3"')
        with self.assertRaisesRegex(ValueError,'versions disagree'):metadata.version(self.root)

    def test_generated_hashes_bind_both_binaries_to_the_build_commit(self):
        for name in ('soloist-capture.exe','opus.dll'):self.pe(name)
        metadata.stamp_native(self.root,self.commit);metadata.verify_native(self.root,self.commit)
        with self.assertRaisesRegex(ValueError,'source commit'):metadata.verify_native(self.root,'b'*40)
        (self.root/'pc/native/opus.dll').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):metadata.verify_native(self.root,self.commit)
        with self.assertRaisesRegex(ValueError,'Windows payload'):metadata.stamp_native(self.root,self.commit)

    def test_a_stale_native_manifest_is_not_accepted(self):
        for name in ('soloist-capture.exe','opus.dll'):self.pe(name)
        metadata.stamp_native(self.root,self.commit)
        (self.root/'pc/native/SHA256SUMS.txt').write_text('outdated checksum')
        with self.assertRaisesRegex(ValueError,'manifest mismatch'):metadata.verify_native(self.root,self.commit)

    def test_vpk_identity_ignores_binary_integer_fields_and_rejects_wrong_version(self):
        (self.root/'build').mkdir()
        cmake=self.root/'CMakeLists.txt'
        cmake.write_text('vita_create_vpk(app.vpk ID VERSION 01.18)\n')
        keys=b'APP_VER\0TITLE_ID\0ATTRIBUTE\0';values=b'01.18\0VRXA00001\0'+struct.pack('<I',0x8000)
        index=b''.join(struct.pack('<HHIII',key,kind,size,size,value) for key,kind,size,value in
                       ((0,0x0204,6,0),(8,0x0204,10,6),(17,0x0404,4,16)))
        sfo=struct.pack('<5I',0x46535000,0x101,20+len(index),20+len(index)+len(keys),3)+index+keys+values
        with zipfile.ZipFile(self.root/'build/vita-audio-receiver.vpk','w') as archive:archive.writestr('sce_sys/param.sfo',sfo)
        metadata.verify_vpk(self.root)
        cmake.write_text('vita_create_vpk(app.vpk ID VERSION 01.17)\n')
        with self.assertRaisesRegex(ValueError,'release source'):metadata.verify_vpk(self.root)

    def test_publish_creates_only_a_draft_and_uploads_canonical_ci_assets(self):
        out=self.assets();runner=self.runner()
        with mock.patch.dict(os.environ,{'GH_REPO':'owner/repository'}):publish_release.prepare(self.root,out,'v1.3.1',self.commit,runner)
        calls=[c.args[0] for c in runner.call_args_list]
        create=next(c for c in calls if c[1:3]==['release','create'])
        self.assertIn('--draft',create);self.assertIn('--verify-tag',create)
        upload=next(c for c in calls if c[1:3]==['release','upload'])
        self.assertIn(str(out/'vita-audio-receiver-1.3.1.zip'),upload)
        self.assertFalse(any(c[1:3]==['release','edit'] for c in calls))

    def test_public_release_or_moved_tag_cannot_be_overwritten(self):
        out=self.assets()
        for runner in (self.runner(draft=False),self.runner(remote='b'*40)):
            with mock.patch.dict(os.environ,{'GH_REPO':'owner/repository'}),self.assertRaises(ValueError):
                publish_release.prepare(self.root,out,'v1.3.1',self.commit,runner)
            self.assertFalse(any(c.args[0][1:3]==['release','upload'] for c in runner.call_args_list))

    def test_tampered_asset_or_wrong_build_identity_blocks_all_remote_calls(self):
        out=self.assets();runner=self.runner()
        (out/'vita-audio-receiver.vpk').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'checksum mismatch'):publish_release.prepare(self.root,out,'v1.3.1',self.commit,runner)
        runner.assert_not_called()
        with self.assertRaisesRegex(ValueError,'Tag/version mismatch'):publish_release.prepare(self.root,out,'v1.3.2',self.commit,runner)

if __name__=='__main__':unittest.main()
