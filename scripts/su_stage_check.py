"""EVT-suite read-only full infrastructure audit, independent of the study reading."""
import json
import sys

from _bootstrap import ROOT  # noqa: F401
from su_analyze import integrity


def check(hub, during_driver=False):
    return integrity(hub, during_driver)[0]


if __name__ == "__main__":
    result = check(sys.argv[1])
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result["complete"] else 1)
