"""Behavioral tests for mandatory-test enforcement in the portable runner."""

import importlib.util
import io
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


def load_verify_portable():
    spec = importlib.util.spec_from_file_location(
        "verify_portable", ROOT / "scripts/verify-portable.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequiredTestRunnerTests(unittest.TestCase):
    def test_missing_required_test_fails_without_running_anything(self):
        module = load_verify_portable()
        output = io.StringIO()

        result = module.run_required_test(
            unittest.TestSuite(), "missing.test", stream=output
        )

        self.assertEqual(result, 1)
        self.assertIn("not found", output.getvalue().casefold())

    def test_skipped_required_test_fails_even_when_unittest_reports_success(self):
        module = load_verify_portable()
        output = io.StringIO()

        @unittest.skip("fixture skip")
        def skipped_fixture():
            pass

        test = unittest.FunctionTestCase(skipped_fixture)
        required_id = test.id()
        result = module.run_required_test(
            unittest.TestSuite([test]), required_id, stream=output
        )

        self.assertEqual(result, 1)
        self.assertIn("skipped", output.getvalue().casefold())


if __name__ == "__main__":
    unittest.main()
