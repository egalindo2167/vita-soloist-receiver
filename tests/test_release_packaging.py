"""Public release privacy and source-completeness invariants."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
spec=importlib.util.spec_from_file_location('package_release',Path(__file__).resolve().parents[1]/'tools/package_release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class ReleasePackagingTests(unittest.TestCase):
    def fixture(self,root,relative,data=b'fixture'):
        path=root/relative;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        return path

    def test_public_archive_keeps_source_policy_and_excludes_private_runtime_and_foreign_binaries(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'project';output=Path(temporary)/'release.zip'
            keep=['.gitignore','.gitattributes','assets/mark.svg','.github/workflows/build.yml',
                  '.github/ISSUE_TEMPLATE/bug_report.yml','src/search_keyboard.c','pc/queue_probe.py',
                  'pc/native/soloist-capture.exe','pc/native/opus.dll','pc/soloist/READ-ME.txt','LICENSE']
            private=['pc/host.json','pc/paired-vitas.json','pc/funnel.json','pc/tunnel.json',
                     'pc/vita-pairing.bin','pc/remote-host.txt','pc/host.log','recordings/private.wav',
                     'pc/soloist/account.json','pc/soloist/soloist.exe','pc/unrelated.exe','pc/unrelated.dll',
                     '.git/config','build/private.py','pc/__pycache__/cached.pyc','pc/secret.json']
            for name in keep+private:self.fixture(root,name)
            self.fixture(root,'pc/favorites.json',b'[]\n')
            vpk=io.BytesIO()
            with zipfile.ZipFile(vpk,'w') as z:z.writestr('eboot.bin',b'test binary')
            self.fixture(root,'build/vita-audio-receiver.vpk',vpk.getvalue())
            with contextlib.redirect_stdout(io.StringIO()):release.package(root,output)
            with zipfile.ZipFile(output) as z:
                prefix='vita-audio-receiver/'
                for name in keep:self.assertIn(prefix+name,z.namelist())
                for name in private:self.assertNotIn(prefix+name,z.namelist())
                self.assertEqual(z.read(prefix+'dist/vita-audio-receiver.vpk'),vpk.getvalue())
                self.assertEqual(json.loads(z.read(prefix+'pc/favorites.json')),[])
                self.assertIsNone(z.testzip())

    def test_populated_favorites_refuse_publication_before_replacing_existing_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)/'project';output=Path(temporary)/'release.zip'
            self.fixture(root,'pc/favorites.json',b'[{"name":"Private favorite"}]')
            output.write_bytes(b'existing release')
            with self.assertRaisesRegex(ValueError,'empty release template'):
                release.package(root,output)
            self.assertEqual(output.read_bytes(),b'existing release')

if __name__=='__main__':unittest.main()
