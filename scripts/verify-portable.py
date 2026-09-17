#!/usr/bin/env python3
"""Run every portable repository test module with Python's standard library."""

import argparse
from pathlib import Path
import sys
import unittest


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def iter_tests(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from iter_tests(test)
        else:
            yield test


def run_required_test(suite, required_test_id, stream=None):
    stream = stream or sys.stderr
    matches = [test for test in iter_tests(suite) if test.id() == required_test_id]
    if len(matches) != 1:
        stream.write(
            f"ERROR: required test {required_test_id!r} not found exactly once "
            f"(found {len(matches)})\n"
        )
        return 1

    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.TestSuite(matches)
    )
    if result.skipped:
        stream.write(f"ERROR: required test {required_test_id!r} was skipped\n")
        return 1
    if result.testsRun != 1:
        stream.write(
            f"ERROR: required test {required_test_id!r} ran {result.testsRun} times\n"
        )
        return 1
    return 0 if result.wasSuccessful() else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--required-test",
        help="run exactly one test by full unittest id and fail if it is missing or skipped",
    )
    args = parser.parse_args(argv)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    if args.required_test:
        return run_required_test(suite, args.required_test)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
