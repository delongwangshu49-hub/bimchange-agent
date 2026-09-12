"""Offline safety checks for release support tooling (no publication)."""
import importlib.util
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComplianceToolTests(unittest.TestCase):
    def test_public_verifier_rejects_missing_or_changed_evidence(self):
        verifier = load_script('verify_release')
        self.assertFalse(verifier.verify(public=True)['public_ready'])
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            roles = ('installer', 'portable', 'qt_sources', 'native_python_sources',
                     'notices', 'payload_manifest', 'frozen_smoke', 'installer_acceptance',
                     'license_review', 'source_inventory')
            files = {}
            for role in roles:
                (root / role).write_bytes(b'original')
                files[role] = {'path': role, 'sha256': hashlib.sha256(b'original').hexdigest()}
            (root / 'release-evidence.json').write_text(json.dumps({'version': '1.0.0', 'files': files}))
            (root / 'installer').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'digest mismatch: installer'):
                verifier.verify_evidence(root)
            files['installer']['path'] = '../outside.exe'
            (root / 'release-evidence.json').write_text(json.dumps({'version': '1.0.0', 'files': files}))
            with self.assertRaises(ValueError):
                verifier.verify_evidence(root)

    def test_occt_exception_and_nested_licenses_are_kept(self):
        collector = load_script("create_dependency_notices")
        self.assertTrue(collector.selected(Path("OCCT_LGPL_EXCEPTION.txt")))
        self.assertTrue(collector.selected(Path("doc/src/legal/licenses.qdoc")))
        self.assertTrue(collector.selected(Path("licenses/LicenseRef-Special.txt")))
        self.assertFalse(collector.selected(Path("model.ifc")))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            content = b"Upstream copyright notice\n"
            with tarfile.open(source / "component.tar.gz", "w:gz") as archive:
                entry = tarfile.TarInfo("component/LICENSE")
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            output = root / "notices"
            collector.collect(source, output)
            with zipfile.ZipFile(output / "UPSTREAM-NOTICES.zip") as archive:
                self.assertEqual(archive.read("component.tar.gz/component/LICENSE"), content)
            result = json.loads((output / "source-inventory.json").read_text())
            self.assertEqual(result["notice_files"], 1)
            self.assertEqual(result["status"], "COLLECTED_REVIEW_REQUIRED")
            with self.assertRaises(FileExistsError):
                collector.collect(source, output)

    def test_notice_collector_refuses_traversal(self):
        collector = load_script("create_dependency_notices")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "sources"
            source.mkdir()
            with tarfile.open(source / "bad.tar.gz", "w:gz") as archive:
                entry = tarfile.TarInfo("../LICENSE")
                entry.size = 1
                archive.addfile(entry, io.BytesIO(b"x"))
            with self.assertRaises(ValueError):
                collector.collect(source, root / "notices")

    def test_installer_test_is_restricted_to_disposable_runner(self):
        script = (ROOT / "scripts/test_release_installer.ps1").read_text()
        for guard in ("GITHUB_ACTIONS", "RUNNER_OS", "RUNNER_TEMP", "Existing stable installation detected",
                      "Existing user preferences detected", "Installed hash mismatch"):
            self.assertIn(guard, script)

    def test_native_source_revisions_are_pinned(self):
        manifest = json.loads((ROOT / "packaging/native-sources.json").read_text())
        for entry in manifest:
            if "commit" in entry:
                self.assertEqual(len(entry["commit"]), 40)
            else:
                self.assertEqual(len(entry["sha256"]), 64)
        script = (ROOT / "scripts/build_ifcopenshell_no_cgal.ps1").read_text()
        self.assertIn("-DWITH_CGAL=OFF", script)
        self.assertIn("-DBUILD_ONLY_COMMON_SCHEMAS=OFF", script)
        self.assertIn("-DBUILD_LIBRARY_TYPE=Shared", script)


if __name__ == "__main__":
    unittest.main()
