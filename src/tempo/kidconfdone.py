"""V1.22.0 KIDCONF-v1 infrastructure qualification and analysis-plan schema (no model).

completion(hub, freeze) -> {"complete": bool, "problems": [...], ...}. Checked independently of the shell driver,
using the runner's own artifacts (scripts/tempo_run.py):
  - per stage (smoke, main): LOCK.json exists, fake = false, calls_sha256 = COMMITMENT-<stage>.json, config_sha256 =
    sha256(HUB/config/stage-<stage>.json) and source_sha256 = the frozen source; END.json exists with finished = true;
    no STOP.json; the stage records equal the stage schedule exactly (no missing / extra / duplicate), all status ok;
  - resources (config/RESOURCE-GUARD.json, config/DEADLINE.json): attempts used (every final record + every logged
    failed attempt, all stages) <= total_attempts; no logged failed attempt (retry_limit 0); every record's
    finished_at and each END.json "at" are no later than the deadline.
Any failure -> INCOMPLETE (no A/C qualification; descriptive tables stay available).

validate_plan(plan) checks the frozen per-component analysis recipe and returns it normalised:
  {"arrival": {"rule": ["P"|"BT", alpha], "threshold": "0"},
   "correction": {"rule": ["P"|"BT", alpha], "threshold": "-3/64"},
   "reference": ["P", 0.025], "B": 10000, "seed": int}
No fallback: a missing or unexpected key raises."""
import hashlib
import json
import time
from fractions import Fraction
from pathlib import Path

from . import refguard as RG

STAGES = ("smoke", "main")
PLAN_KEYS = {"arrival", "correction", "reference", "B", "seed"}


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def _epoch(local_iso):
    """Runner timestamps: '%Y-%m-%dT%H:%M:%S' local time (END 'at', record finished_at)."""
    return time.mktime(time.strptime(local_iso[:19], "%Y-%m-%dT%H:%M:%S"))


def _load(p):
    return [json.loads(l) for l in Path(p).read_text().splitlines() if l.strip()]


def completion(hub, source_sha256):
    hub = Path(hub)
    probs, info = [], {}
    try:
        guard = json.loads((hub / "config" / "RESOURCE-GUARD.json").read_text())
        dl = json.loads((hub / "config" / "DEADLINE.json").read_text())["deadline_epoch"]
    except (OSError, ValueError, KeyError) as e:
        return {"complete": False, "problems": [f"resource policy files missing or invalid: {e!r}"[:200]]}
    for st in STAGES:
        sd = hub / "stages" / st
        try:
            lock = json.loads((sd / "LOCK.json").read_text())
            commit = json.loads((hub / "data" / f"COMMITMENT-{st}.json").read_text())
            want_lock = {"config_sha256": _sha(hub / "config" / f"stage-{st}.json"),
                         "calls_sha256": commit["calls_sha256"], "source_sha256": source_sha256, "fake": False}
            if lock != want_lock:
                probs.append(f"{st}: LOCK does not bind the committed config/calls/source or is fake")
        except (OSError, ValueError, KeyError):
            probs.append(f"{st}: LOCK or commitment missing")
        end = sd / "END.json"
        if not end.exists():
            probs.append(f"{st}: no END.json")
        else:
            e = json.loads(end.read_text())
            if e.get("finished") is not True:
                probs.append(f"{st}: END.json not finished")
            elif _epoch(e["at"]) > dl:
                probs.append(f"{st}: END after the deadline")
        if (sd / "STOP.json").exists():
            probs.append(f"{st}: STOP.json present (stage stopped before finishing)")
        if (sd / "attempts.jsonl").exists() and any(l.strip() for l in (sd / "attempts.jsonl").read_text().splitlines()):
            probs.append(f"{st}: logged failed attempts")
        sched = [c["call_id"] for c in _load(hub / "data" / f"{st}-calls.jsonl")]
        recs, n_files = {}, 0
        for p in sorted((sd / "calls").glob("*.json")) if (sd / "calls").exists() else []:
            r = json.loads(p.read_text())
            n_files += 1
            if r["call_id"] in recs:
                probs.append(f"{st}: duplicate record {r['call_id']}")
            recs[r["call_id"]] = r
        if set(recs) != set(sched) or len(sched) != len(set(sched)):
            probs.append(f"{st}: records != schedule ({len(set(sched) - set(recs))} missing, {len(set(recs) - set(sched))} extra)")
        if any(r.get("status") != "ok" for r in recs.values()):
            probs.append(f"{st}: records not ok")
        late = [c for c, r in recs.items() if "finished_at" not in r or _epoch(r["finished_at"]) > dl]
        if late:
            probs.append(f"{st}: {len(late)} records finished after the deadline or undated")
        info[st] = {"scheduled": len(sched), "records": n_files}
    used = RG.used_attempts(hub)
    info["attempts_used"] = used
    info["attempt_ceiling"] = guard["total_attempts"]
    if used > guard["total_attempts"]:
        probs.append(f"attempt budget exceeded: {used} > {guard['total_attempts']}")
    return {"complete": not probs, "problems": probs, **info}


def plan_sha256(plan):
    """Canonical hash of a plan's contents (sorted keys, compact separators); the freeze records this value."""
    return hashlib.sha256(json.dumps(plan, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_plan(plan):
    if set(plan) != PLAN_KEYS:
        raise ValueError(f"plan keys {sorted(plan)} != {sorted(PLAN_KEYS)}")
    out = {"B": plan["B"], "seed": plan["seed"]}
    if not isinstance(plan["B"], int) or plan["B"] < 1000 or not isinstance(plan["seed"], int):
        raise ValueError("B must be an int >= 1000 and seed an int")
    want_thr = {"arrival": Fraction(0), "correction": -Fraction(3, 64)}
    for comp in ("arrival", "correction"):
        c = plan[comp]
        if set(c) != {"rule", "threshold"}:
            raise ValueError(f"{comp}: keys {sorted(c)}")
        fam, alpha = c["rule"]
        if fam not in ("P", "BT") or not (isinstance(alpha, float) and 0 < alpha < 0.5):
            raise ValueError(f"{comp}: rule {c['rule']}")
        if Fraction(c["threshold"]) != want_thr[comp]:
            raise ValueError(f"{comp}: threshold {c['threshold']} is not the declared {want_thr[comp]}")
        out[comp] = {"rule": (fam, alpha), "threshold": Fraction(c["threshold"])}
    ref = tuple(plan["reference"])
    if ref != ("P", 0.025):
        raise ValueError("reference interval must be the labelled 95% percentile reference ['P', 0.025]")
    out["reference"] = ref
    return out
