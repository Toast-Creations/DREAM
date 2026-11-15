"""CCONF-v1 read-only full infrastructure audit, independent of semantic gates."""
import json
import sys

from _bootstrap import ROOT  # noqa: F401
from cc_analyze import integrity


def check(hub):
    return integrity(hub)[0]


if __name__ == "__main__":
    result = check(sys.argv[1])
    print(json.dumps(result, sort_keys=True))
    sys.exit(0 if result["complete"] else 1)
