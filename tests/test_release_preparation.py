"""Release identity, retained assets and synthetic-only illustration regression."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"scripts/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class ReleasePreparationTests(unittest.TestCase):
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
