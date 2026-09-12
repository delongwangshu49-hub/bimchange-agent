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
    def test_boost_headers_cover_direct_includes_and_preserve_existing_bytes(self):
        preparer = load_script('prepare_boost_headers')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for module, name in (('logic', 'logic/tribool.hpp'), ('uuid', 'uuid/uuid.hpp'),
                                 ('numeric/ublas', 'numeric/ublas/matrix.hpp')):
                path = root/'boost/libs'/module/'include/boost'/name
                path.parent.mkdir(parents=True)
                path.write_bytes(b'upstream\r\n')
            for directory in ('ifcparse', 'ifcgeom', 'ifcwrap', 'serializers'):
                (root/'ifc/src'/directory).mkdir(parents=True)
            (root/'ifc/src/ifcparse/test.h').write_text('#include <boost/numeric/ublas/matrix.hpp>\n')
            result = preparer.complete_headers(root/'boost', root/'include', root/'ifc')
            self.assertEqual(result['header_files'], 3)
            self.assertEqual((root/'include/boost/logic/tribool.hpp').read_bytes(), b'upstream\r\n')
            (root/'include/boost/logic/tribool.hpp').write_bytes(b'different')
            with self.assertRaisesRegex(ValueError, 'differs from source'):
                preparer.complete_headers(root/'boost', root/'include', root/'ifc')
            self.assertEqual((root/'include/boost/logic/tribool.hpp').read_bytes(), b'different')
            (root/'ifc/src/ifcparse/test.h').write_text('#include <boost/absent.hpp>\n')
            with self.assertRaisesRegex(ValueError, 'headers absent'):
                preparer.complete_headers(root/'boost', root/'new-include', root/'ifc')
            self.assertFalse((root/'new-include').exists())

    def test_native_pipeline_preflights_headers_and_saves_occt_before_ifc(self):
        workflow = (ROOT/'.github/workflows/native-ifc.yml').read_text()
        self.assertLess(workflow.index('Build Boost and preflight'), workflow.index('Build OpenCASCADE'))
        self.assertLess(workflow.index('actions/cache/save@v4'), workflow.index('Build IfcOpenShell without CGAL'))
        self.assertIn('native-ifc-built-dependencies', workflow)

    def test_native_extractor_preserves_bytes_and_refuses_overwrite(self):
        extractor = load_script('extract_native_source')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with tarfile.open(root/'source.tar', 'w') as archive:
                entry = tarfile.TarInfo('component/include/test.h')
                content = b'exact upstream bytes\r\n'
                entry.size = len(content)
                archive.addfile(entry, io.BytesIO(content))
            result = extractor.extract(root/'source.tar', root/'output')
            self.assertEqual(result['files'], 1)
            self.assertEqual((root/'output/include/test.h').read_bytes(), content)
            self.assertTrue((root/'output/.source-extraction-complete.json').is_file())
            with self.assertRaises(FileExistsError):
                extractor.extract(root/'source.tar', root/'output')

    def test_native_extractor_rejects_traversal_links_and_multiple_roots(self):
        extractor = load_script('extract_native_source')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for index, name in enumerate(('component/../escape', '/absolute', 'component/C:escape', 'second/file')):
                archive_path = root/f'{index}.tar'
                with tarfile.open(archive_path, 'w') as archive:
                    archive.addfile(tarfile.TarInfo('component/first'))
                    archive.addfile(tarfile.TarInfo(name))
                with self.assertRaises(ValueError):
                    extractor.extract(archive_path, root/f'output{index}')
                self.assertFalse((root/f'output{index}/.source-extraction-complete.json').exists())
            with tarfile.open(root/'link.tar', 'w') as archive:
                entry = tarfile.TarInfo('component/link')
                entry.type = tarfile.SYMTYPE
                entry.linkname = '../outside'
                archive.addfile(entry)
            with self.assertRaises(ValueError):
                extractor.extract(root/'link.tar', root/'linked')

    def test_complete_evidence_is_bound_to_payload_and_sources(self):
        verifier = load_script('verify_release')
        digest = lambda content: hashlib.sha256(content).hexdigest()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entries = {}
            def put(role, data):
                content = json.dumps(data).encode() if isinstance(data, dict) else data
                (root / role).write_bytes(content)
                entries[role] = {'path': role, 'sha256': digest(content)}
            put('installer', b'installer')
            put('portable', b'portable')
            put('notices', b'notices')
            put('payload_manifest', {'status': 'PASS', 'files': [{'path': 'BIMChange-Agent.exe', 'sha256': digest(b'executable')}],
                                     'zip': {'sha256': entries['portable']['sha256']}})
            installed = {key: True for key in ('fresh_install', 'desktop_startup', 'offline_comparison',
                         'preferences_preserved', 'shortcut_target_and_icon',
                         'uninstall_executable_and_registry_removed', 'input_files_unchanged')}
            installed.update(status='PASS', installer_sha256=entries['installer']['sha256'],
                             payload_manifest_sha256=entries['payload_manifest']['sha256'],
                             payload_files_verified=1, upgrade_from='0.9.0')
            put('installer_acceptance', installed)
            put('frozen_smoke', {'status': 'PASS', 'frozen': True, 'errors': [], 'session_removed': True,
                                 'executable_sha256': digest(b'executable')})
            put('license_review', {'status': 'PASS', 'payload_manifest_sha256': entries['payload_manifest']['sha256']})
            source_entries = []
            for role in ('qt_sources', 'native_python_sources'):
                archive_name = role+'.tar.gz'
                with zipfile.ZipFile(root / role, 'w') as archive:
                    archive.writestr(archive_name, b'source')
                entries[role] = {'path': role, 'sha256': digest((root / role).read_bytes())}
                source_entries.append({'file': archive_name, 'sha256': digest(b'source')})
            put('source_inventory', {'notice_zip_sha256': entries['notices']['sha256'], 'archives': source_entries})
            evidence = {'version': '1.0.0', 'files': entries,
                        'smoke_payload_manifest_sha256': entries['payload_manifest']['sha256']}
            (root / 'release-evidence.json').write_text(json.dumps(evidence))
            self.assertEqual(verifier.verify_evidence(root), 10)
            installed['installer_sha256'] = digest(b'different installer')
            put('installer_acceptance', installed)
            (root / 'release-evidence.json').write_text(json.dumps(evidence))
            with self.assertRaisesRegex(ValueError, 'different artifacts'):
                verifier.verify_evidence(root)

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
