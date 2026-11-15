"""Prepare a new offline run hub using a separately qualified controller copy.

This script prepares files only. The controller template must contain
pilot_entry.py, pilot_supervisor.py and harness.py. No weights are copied.
V1.2.0 adds ``--study decategorization``; its default stages stop after
vector qualification, smoke and dose-finding. The pilot is opt-in by name.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import shutil
from zoneinfo import ZoneInfo
from _bootstrap import ROOT
from dream_core.config import load_config
from dream_core.ledger import file_hash, atomic_json
from dream_core.planning import trial_count

STUDIES = {
    "concepts": {"data": ("concepts-development.jsonl", "concepts-smoke.jsonl"),
                 "stages": ("concepts-smoke", "concepts-pilot"), "hub": "concept-reasoning",
                 "authorization": "Update research packages and compare reasoning; broad mix of concepts selected in chat on 2026-10-30.",
                 "primary_contrast": "reasoning on minus off at zero steering; relevance-gated quality of five associations, blinded ratings",
                 "expectation": "David expects reasoning to improve results; not an observed finding.",
                 "execution_assistance": "Codex", "vector_direction": None, "runtime_extra": ()},
    "decategorization": {"data": ("objects-development.jsonl", "objects-smoke.jsonl", "objects-dosefind.jsonl"),
                 "stages": ("decat-smoke", "decat-dosefind"), "hub": "decategorization",
                 "authorization": "Record the specific chat authorization here before launch; this source was built without run authorization.",
                 "primary_contrast": "trip and two-step arms versus zero-dose controls; blinded idea review",
                 "expectation": "David expects strange output under high interference to contain ideas worth exploring once sobered; not an observed finding.",
                 "execution_assistance": "Claude", "vector_direction": "decategorization",
                 # The worker binds runtime-data over /project/data, so vector
                 # qualification needs its contrast files copied there too.
                 "runtime_extra": ("decategorization_prompts.json", "steering_prompts.json")},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-template", required=True)
    parser.add_argument("--model-directory", required=True)
    parser.add_argument("--model-manifest", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--study", choices=sorted(STUDIES), default="concepts")
    parser.add_argument("--stages", nargs="+", help="Config stems to queue, in order (default: the study's own)")
    args = parser.parse_args()
    study = STUDIES[args.study]
    stages = args.stages or list(study["stages"])
    template = Path(args.controller_template).resolve()
    manifest = json.loads(Path(args.model_manifest).read_text())
    stamp = datetime.now(ZoneInfo("America/New_York")).strftime("%Y%m%d-%H%M%S")
    hub = Path(args.output_root).resolve() / f"{study['hub']}-{stamp}"
    run = hub / "run"; out = hub / "output"
    run.mkdir(parents=True, exist_ok=False); out.mkdir()
    shutil.copytree(ROOT, run / "project", ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "dist", "temporary", "runs"))
    for name in ("inputs/configs", "inputs/data", "controller", "runtime-data", "scratch",
                 "results/testing", "results/artifacts", "results/runs", "results/stages", "results/qualification"):
        (run / name).mkdir(parents=True, exist_ok=True)
    for name in ("pilot_entry.py", "pilot_supervisor.py", "harness.py"):
        shutil.copy2(template / name, run / "controller" / name)
    shutil.copy2(args.model_manifest, run / "inputs/model-manifest.json")
    for name in study["data"]:
        rows = [json.loads(x) for x in (ROOT / "data" / name).read_text().splitlines() if x.strip()]
        if any(x["split"] != "development" for x in rows):
            raise ValueError("Only development items may enter this worker")
        shutil.copy2(ROOT / "data" / name, run / "inputs/data" / name)
        shutil.copy2(ROOT / "data" / name, run / "runtime-data" / name)
    for name in study["runtime_extra"]:
        shutil.copy2(ROOT / "data" / name, run / "runtime-data" / name)
    expected = {}
    for stage in stages:
        cfg = json.loads((ROOT / "configs" / f"{stage}.json").read_text())
        expected[stage] = trial_count(load_config(ROOT / "configs" / f"{stage}.json"),
                                      sum(json.loads(x)["split"] == cfg["phase"] for x in
                                          (ROOT / "data" / Path(cfg["data_path"]).name).read_text().splitlines() if x.strip()))
        cfg["model"].update(path="/model", manifest="/inputs/model-manifest.json")
        cfg["data_path"] = "/inputs/data/" + Path(cfg["data_path"]).name
        cfg["output_dir"] = "/results/runs/" + stage
        for key in ("vector_path", "random_vector_path", "divergent_vector_path"):
            if cfg["steering"].get(key):
                # All stages share one hub-qualified artifact set.
                cfg["steering"][key] = "/results/artifacts/" + Path(cfg["steering"][key]).name
        atomic_json(run / "inputs/configs" / f"{stage}.json", cfg)
    def inventory(path):
        return [{"path":p.relative_to(path).as_posix(), "sha256":file_hash(p)}
                for p in sorted(path.rglob("*")) if p.is_file()]
    atomic_json(out / "run-plan.json", {
        "project_lead":"David Cook", "execution_assistance":study["execution_assistance"],
        "authorization":study["authorization"], "study":args.study, "stages":stages,
        "expected_trials":expected, "vector_direction":study["vector_direction"],
        "run_directory":str(run), "output_directory":str(out), "source_directory":str(ROOT),
        "model_directory":str(Path(args.model_directory).resolve()),
        "model_id":manifest["model_id"], "model_revision":manifest["revision"],
        "primary_contrast":study["primary_contrast"], "expectation":study["expectation"],
        "study_status":"development-only exploratory; queued stages: " + ", ".join(stages),
        "limits":{"gpu_worker_bytes":23*1024**3, "worker_rss_bytes":8*1024**3,
                  "output_bytes":2*1024**3, "prelaunch_available_host_bytes":6*1024**3,
                  "prelaunch_free_gpu_bytes":20*1024**3},
        "welfare_policy":"Pause and preserve on a distress/stop trigger in answers or reasoning; never resume automatically. Pattern coverage is limited.",
        "source_inventory":inventory(run / "project"), "input_inventory":inventory(run / "inputs"),
        "controller_sha256":{p.name:file_hash(p) for p in (run / "controller").iterdir() if p.is_file()}})
    print(hub)


if __name__ == "__main__":
    main()
