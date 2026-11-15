"""Dedicated CCONF freeze entry point; identical to cc_prepare.py freeze."""
import sys
from cc_prepare import main

if __name__ == "__main__":
    sys.argv.insert(1, "freeze")
    main()
