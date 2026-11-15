"""Record passing, failing, and skipped checks without disguising missing ML tests.

The core suite runs without model downloads. Optional integration tests build a
tiny random local transformer when the ML packages exist. A logic-only success
is not model-runtime validation: the experiment launcher independently requires
ml_dependencies_available=True, skipped=0, success=True, and a matching digest.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from _bootstrap import ROOT
from dream_core.ledger import release_source_hash


def main():
    """Discover tests, emit a source-bound coverage record, and select exit status."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report",default=str(ROOT/"test-results"/"latest.json"))
    parser.add_argument("--require-ml",action="store_true")
    args=parser.parse_args()
    # Availability is module discovery, not a tested compatibility claim. The
    # tests must actually import/run the stack to establish integration coverage.
    available=all(importlib.util.find_spec(x) is not None for x in ("torch","transformers","peft","safetensors"))
    suite=unittest.defaultTestLoader.discover(str(ROOT/"tests"))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    report={"version":"1.6.4","tests_run":result.testsRun,"failures":len(result.failures),
        "errors":len(result.errors),"skipped":len(result.skipped),"ml_dependencies_available":available,
        "passed":result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
        "skipped_tests":[{"test":str(t),"reason":r} for t,r in result.skipped],
        "success":result.wasSuccessful() and (available or not args.require_ml),
        "source_sha256":release_source_hash(ROOT)}
    path=Path(args.report); path.parent.mkdir(parents=True,exist_ok=True)
    # This runner overwrites its requested report path intentionally. Historical
    # evidence belongs in a preserved copy; the report is not an authenticated
    # external attestation. Its digest coverage is documented in ledger.py.
    path.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    if args.require_ml and not available: print("Required ML integration coverage is unavailable",file=sys.stderr)
    return 0 if report["success"] else 1


if __name__=="__main__": sys.exit(main())
