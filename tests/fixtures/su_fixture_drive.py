"""Isolated CPU fixture: run the actual EVT-suite driver on a hub with the CPU fixture worker. Never study evidence.

Arguments: --hub HUB --manifest TEST_MANIFEST [--main-mode MODE] [--gpu ok|busy]. Used by the chain tests as the child command.
"""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import su_certify as SCERT  # noqa: E402
import su_run as SR  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--hub", required=True)
ap.add_argument("--main-mode", default="better")
ap.add_argument("--gpu", default="ok")
ap.add_argument("--manifest", required=True)
a = ap.parse_args()
SCERT.MANIFEST_PATH = a.manifest  # explicit fixture injection


def worker(hub, stage, remaining):
    return [sys.executable, "-B", str(ROOT / "tests/fixtures/su_cpu_runner.py"), "--hub", str(hub), "--stage", stage,
            "--config", str(Path(hub) / f"config/stage-{stage}.json"),
            "--mode", a.main_mode if stage == "main" else "equal"]


def gpu():
    if a.gpu == "busy":
        raise RuntimeError("GPU is busy")
    return {"fixture": True}


sys.exit(SR.drive(a.hub, worker=worker, gpu_probe=gpu, notify=False))
