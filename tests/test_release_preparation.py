"""Release identity, retained assets and synthetic-only illustration regression."""
import importlib.util
import runpy
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ReleasePreparationTests(unittest.TestCase):
    def test_desktop_smoke_diff_uses_current_r3_entry(self):
        from PySide6.QtWidgets import QApplication
        from bimchange_agent import desktop_app
        app = QApplication.instance() or QApplication([])
        self.assertIsNotNone(app)
        with patch.object(sys, "argv", ["app", "--smoke-diff", "source.ifc", "revised.ifc", "out"]), \
             patch.object(desktop_app, "diff_ifc_pair_r3") as compare:
            self.assertEqual(desktop_app.main(), 0)
            compare.assert_called_once_with(Path("source.ifc"), Path("revised.ifc"), Path("out"))
            compare.side_effect = ValueError("controlled failure")
            self.assertEqual(desktop_app.main(), 2)

    def test_qt_hooks_keep_native_dependencies_and_filter_unused_plugins(self):
        qt = types.ModuleType("PyInstaller.utils.hooks.qt")
        source_entries = [("runtime.dll", "PySide6"),
                          ("qwindows.dll", "PySide6/plugins/platforms")]
        cases = {"QtGui": ["generic", "platforminputcontexts"],
                 "QtQml": ["qmltooling"], "QtPositioning": ["position"]}
        for name, excluded in cases.items():
            entries = source_entries + [("unused.dll", f"PySide6/plugins/{p}") for p in excluded]
            qt.add_qt6_dependencies = lambda _: (["native-import"], entries, [("data", "resources")])
            with patch.dict(sys.modules, {"PyInstaller.utils.hooks.qt": qt}):
                result = runpy.run_path(str(ROOT / f"packaging/hooks/hook-PySide6.{name}.py"))
            self.assertEqual(result["binaries"], source_entries)
            self.assertEqual(result["hiddenimports"], ["native-import"])
            self.assertEqual(result["datas"], [("data", "resources")])

    def test_qt_inventory_rejects_new_module_and_missing_bundle(self):
        auditor = module("audit_qt_bundle")
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(ValueError):
                auditor.audit(temporary)
            qt_root = Path(temporary) / "_internal/PySide6"
            qt_root.mkdir(parents=True)
            for name in auditor.EXPECTED_QT_MODULES:
                (qt_root / f"Qt6{name}.dll").touch()
            self.assertEqual(auditor.audit(temporary)["status"], "PASS")
            (qt_root / "Qt6VirtualKeyboard.dll").touch()
            with self.assertRaises(ValueError):
                auditor.audit(temporary)

    def test_release_identity_links_and_original_logo(self):
        result = module("verify_release").verify()
        self.assertEqual(result["failures"], [])

    def test_public_mode_reports_unsatisfied_gates(self):
        result = module("verify_release").verify(public=True)
        if result["pending_public_gates"]:
            self.assertEqual(result["status"], "FAIL")
            self.assertFalse(result["public_ready"])

    def test_public_demo_has_actual_i_profile_and_refuses_overwrite(self):
        import ifcopenshell
        generator = module("generate_public_demo")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "demo"
            source, revised, report = generator.generate(output)
            for path in (source, revised):
                model = ifcopenshell.open(path)
                self.assertEqual(len(model.by_type("IfcIShapeProfileDef")), 1)
            self.assertTrue(report.is_file())
            with self.assertRaises(FileExistsError):
                generator.generate(output)
