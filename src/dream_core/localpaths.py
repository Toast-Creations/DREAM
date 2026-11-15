"""Local resource locations, configurable through environment variables.

The research runs used fixed absolute paths on one desktop. The public release reads
them from the environment instead, so the same scripts work on any machine:

    DREAM_HOME    project folder holding Runs/ and Code/        (default ~/DREAM)
    DREAM_RUNS    run hubs with study outputs                    (default $DREAM_HOME/Runs)
    DREAM_CODE    archived per-version source copies (optional)  (default $DREAM_HOME/Code)
    DREAM_MODELS  local model store                              (default ~/DREAM-models)
    DREAM_PY      Python interpreter for child model runs        (default: this interpreter)

Values are plain strings so they can be used wherever the original literal paths were.
"""
import os
import sys


def _env(name, default):
    value = os.environ.get(name)
    return os.path.expanduser(value) if value else default


HOME = _env("DREAM_HOME", os.path.expanduser("~/DREAM"))
RUNS = _env("DREAM_RUNS", os.path.join(HOME, "Runs"))
CODE = _env("DREAM_CODE", os.path.join(HOME, "Code"))
MODELS = _env("DREAM_MODELS", os.path.expanduser("~/DREAM-models"))
PY = _env("DREAM_PY", sys.executable)
