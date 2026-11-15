"""Event contract v1 and assertion engine v0.3 (DREAM 1.9.0). Engine v0.2 (tempo.engine) stays the scored historical
engine; nothing here changes it. See the run hub's design/EVENT-CONTRACT.md.

Report (public, contract v1):
  {"rid": str, "received_at": int, "status": "verified"|"provisional", "type": "state"|"event"|"correction",
   "assertions": [ ... one or more ... ], optional "source", "evidence"}
  state       {"field", "at": int, "value": v}  or  {"field", "at": int, "options": [v1, v2, ...]}
  event       {"field", "at": int, "to": v}  or  {"field", "at": int, "to_options": [...]}, optional "from": v|null
              (absent or null = the source did not state the prior value; nothing is invented)
  correction  {"field", "target": rid, "value": v, "valid_from": int}
  every assertion may carry "evidence" (a quoted span).

Meaning (per field; fields are independent in this record language):
  - A trajectory is a starting value (any value of the field's domain, before all evidence), then every event about
    the field in time order (an event at t takes effect at t; ties by reception order). An event with a stated
    "from" requires the value just before it to equal "from"; an unstated "from" places no requirement.
  - State assertions and corrections are constraints: the value at their time must be in their set. No container
    type is a setter, so a later statement can never reset a timeline (the v0.1/v0.2 "initial" mismatch).
  - A correction withdraws exactly its target report's assertion about its field (the target's other assertions
    stand) and asserts its own value from valid_from.
  - Supported value at t = the set of values at t over consistent trajectories (one value, or "unknown" with
    options). A field with no assertion or event at or before t is "not yet described".
  - Provisional assertions are accepted until withdrawn. If a field's evidence is jointly inconsistent and dropping
    provisional assertions restores consistency with the verified evidence, exactly the provisional assertions that
    are inconsistent with the verified evidence are *suspended* ("contradicted provisional"): verified evidence
    outranks provisional evidence. Nothing physical is inferred: no event is created; the retrospective view over the
    suspended interval follows persistence (rule 1) and is marked as derived.
  - If verified evidence is itself inconsistent, the field is a *conflict*: no value is chosen, both sides are kept,
    and the reports whose removal would restore consistency are listed as culprit candidates.
  - Reports that could not be processed (pending, as in v0.2) make the fields they name "incomplete".
Structural problems (keys, types, unregistered fields, values outside the domain, a correction whose target did not
assert the field, reception order, duplicate IDs) are rejected with a code; consistency is never a rejection.
"""
import copy
import itertools
import json
import os

from . import engine as E

TYPES = ("state", "event", "correction")
STATUSES = ("verified", "provisional")
REPORT_KEYS = {"rid", "received_at", "status", "type", "assertions", "source", "evidence"}
CONTRACT_CODES = {
    "schema": "a report needs rid, received_at, status, type and a non-empty list of assertions, with the keys of its type",
    "time_type": "times must be integers",
    "time_order": "an assertion cannot be about a time after the report was received",
    "reception_order": "reports must arrive in reception order",
    "duplicate_rid": "each report ID may be used once",
    "unregistered_field": "fields must be listed entity attributes",
    "value": "values must be in the field's domain",
    "correction_target": "a correction must name an earlier report that asserted that field",
}


class ContractRejected(E.EngineError):
    def __init__(self, message, code):
        super().__init__(message)
        assert code in CONTRACT_CODES, code
        self.code = code


def _isint(x):
    return isinstance(x, int) and not isinstance(x, bool)


# ====================================================================== mapping from the old record language

def from_v02(r):
    """Canonical mapping of a v0.2 public record to a contract-v1 report (used for fixtures and replays)."""
    p, k = r["payload"], r["kind"]
    base = {"rid": r["rid"], "received_at": r["received_at"], "status": r["status"]}
    for extra in ("source", "evidence"):
        if extra in r:
            base[extra] = r[extra]
    if k == "initial":
        return dict(base, type="state", assertions=[{"field": f, "at": r["event_at"], "value": v}
                                                     for f, v in p["assign"].items()])
    if k == "observation":
        return dict(base, type="state", assertions=[{"field": p["field"], "at": r["event_at"], "value": p["value"]}])
    if k == "change":
        return dict(base, type="event", assertions=[{"field": p["field"], "at": r["event_at"], "from": p["from"],
                                                      "to": p["to"]}])
    if k == "uncertain_change":
        a = {"field": p["field"], "at": r["event_at"], "to_options": list(p["options"])}
        if p.get("from") is not None:
            a["from"] = p["from"]
        return dict(base, type="event", assertions=[a])
    if k == "correction":
        return dict(base, type="correction", assertions=[{"field": p["field"], "target": p["target"],
                                                          "value": p["value"], "valid_from": p["valid_from"]}])
    raise ValueError(k)


# ====================================================================== per-field resolution

def _val(traj, t):
    v = traj[0][1]
    for when, value in traj[1:]:
        if when <= t:
            v = value
    return v


def _trajs(domain, events, constraints):
    evs = sorted(events, key=lambda e: (e["at"], e["ordinal"]))
    for v0 in domain:
        for choice in itertools.product(*[e["to"] for e in evs]):
            traj, cur, ok = [(None, v0)], v0, True
            for e, to in zip(evs, choice):
                if e["from"] is not None and e["from"] != cur:
                    ok = False
                    break
                cur = to
                traj.append((e["at"], cur))
            if ok and all(_val(traj, c["at"]) in c["set"] for c in constraints):
                yield traj


def _any(domain, events, constraints):
    return next(_trajs(domain, events, constraints), None) is not None


def field_items(reports, f):
    withdrawn = {(a["target"], a["field"]): r["rid"] for r in reports if r["type"] == "correction"
                 for a in r["assertions"]}
    cons, evs, withdrawn_here = [], [], []
    for r in reports:
        for a in r["assertions"]:
            if a["field"] != f:
                continue
            if r["type"] == "state":
                if (r["rid"], f) in withdrawn:
                    withdrawn_here.append({"rid": r["rid"], "by": withdrawn[(r["rid"], f)]})
                    continue
                s = {a["value"]} if "value" in a else set(a["options"])
                cons.append({"at": a["at"], "set": s, "rid": r["rid"], "status": r["status"], "kind": "state"})
            elif r["type"] == "event":
                to = [a["to"]] if "to" in a else list(a["to_options"])
                evs.append({"at": a["at"], "from": a.get("from"), "to": to, "rid": r["rid"], "ordinal": r["ordinal"],
                            "status": r["status"]})
            else:
                cons.append({"at": a["valid_from"], "set": {a["value"]}, "rid": r["rid"], "status": "verified",
                             "kind": "correction"})
    return cons, evs, withdrawn_here


def resolve_field(domain, reports, f, t):
    cons, evs, withdrawn = field_items(reports, f)
    times = [c["at"] for c in cons] + [e["at"] for e in evs]
    out = {"field": f, "withdrawn": withdrawn, "suspended": [], "culprits": [], "provisional_support": False,
           "support": sorted({c["rid"] for c in cons} | {e["rid"] for e in evs})}
    if not times or min(times) > t:
        return dict(out, status="not_yet_described")
    used = cons
    if not _any(domain, evs, cons):
        ver = [c for c in cons if c["status"] == "verified"]
        prov = [c for c in cons if c["status"] == "provisional"]
        if prov and _any(domain, evs, ver):
            bad = [p for p in prov if not _any(domain, evs, ver + [p])]
            keep = [p for p in prov if p not in bad]
            if not _any(domain, evs, ver + keep):
                bad, keep = prov, []
            used = ver + keep
            out["suspended"] = sorted({p["rid"] for p in bad})
        else:
            rids = sorted({c["rid"] for c in cons} | {e["rid"] for e in evs})
            out["culprits"] = [rid for rid in rids
                               if _any(domain, [e for e in evs if e["rid"] != rid], [c for c in cons if c["rid"] != rid])]
            return dict(out, status="conflict")
    vals = sorted({_val(tr, t) for tr in _trajs(domain, evs, used)})
    st = dict(out, status="value" if len(vals) == 1 else "unknown", value=vals[0] if len(vals) == 1 else E.UNKNOWN,
              options=vals if len(vals) > 1 else None)
    prov_used = [c for c in used if c["status"] == "provisional"]
    if prov_used:
        nop = [c for c in used if c["status"] != "provisional"]
        vals2 = sorted({_val(tr, t) for tr in _trajs(domain, evs, nop)}) if _any(domain, evs, nop) else None
        st["provisional_support"] = vals2 != vals
    if out["suspended"]:
        st["derived_by_persistence"] = True
    return st


# ====================================================================== engine

class AssertionEngine:
    """Same world spec and action definitions as engine v0.2; contract-v1 reports underneath."""

    def __init__(self, spec, context="ctx"):
        self.spec = spec if isinstance(spec, E.WorldSpec) else E.WorldSpec(spec)
        self.log = E.EvidenceLog(context)
        self.actions = E.Engine(self.spec, context)  # used only for its action definitions and checks
        self._cache = {}

    # ---------------------------------------------------------------- ingest
    def reports(self, cutoff=None):
        out = []
        for e in self.log.entries:
            if e["type"] == "report" and (cutoff is None or e["body"]["received_at"] <= cutoff):
                r = copy.deepcopy(e["body"]); r["ordinal"] = e["seq"]
                out.append(r)
        return out

    def pending(self, cutoff=None):
        return [e["body"] for e in self.log.entries if e["type"] == "pending"
                and (cutoff is None or e["body"]["received_at"] <= cutoff)]

    def _validate(self, r):
        rej = ContractRejected
        if not isinstance(r, dict) or set(r) - REPORT_KEYS or not {"rid", "received_at", "status", "type",
                                                                     "assertions"} <= set(r):
            raise rej("report keys outside the contract", "schema")
        if not isinstance(r["rid"], str) or r["status"] not in STATUSES or r["type"] not in TYPES:
            raise rej("bad rid, status or type", "schema")
        if not _isint(r["received_at"]):
            raise rej("received_at must be an integer", "time_type")
        A = r["assertions"]
        if not isinstance(A, list) or not A:
            raise rej("assertions must be a non-empty list", "schema")
        prior = self.reports()
        if any(x["rid"] == r["rid"] for x in prior):
            raise rej(f"duplicate rid {r['rid']}", "duplicate_rid")
        if prior and r["received_at"] < prior[-1]["received_at"]:
            raise rej("reception order", "reception_order")
        allowed = {"state": ({"field", "at"}, [{"value"}, {"options"}], {"evidence"}),
                   "event": ({"field", "at"}, [{"to"}, {"to_options"}], {"evidence", "from"}),
                   "correction": ({"field", "target", "value", "valid_from"}, [set()], {"evidence"})}[r["type"]]
        req, one_of, opt = allowed
        for a in A:
            if not isinstance(a, dict) or not req <= set(a) or set(a) - req - opt - set().union(*one_of) or \
                    sum(1 for o in one_of if o and o <= set(a)) != (1 if one_of[0] else 0):
                raise rej(f"assertion keys for {r['type']}: {sorted(a) if isinstance(a, dict) else a}", "schema")
            f = a["field"]
            if not isinstance(f, str) or not self.spec.field_ok(f):
                raise rej(f"field {f} not registered", "unregistered_field")
            tkey = "valid_from" if r["type"] == "correction" else "at"
            if not _isint(a[tkey]):
                raise rej(f"{tkey} must be an integer", "time_type")
            if r["type"] != "correction" and a["at"] > r["received_at"]:
                raise rej("assertion about a time after reception", "time_order")
            vals = [a[k] for k in ("value", "to", "from") if k in a and a[k] is not None] + \
                list(a.get("options") or []) + list(a.get("to_options") or [])
            if ("options" in a and (not isinstance(a["options"], list) or len(a["options"]) < 2)) or \
                    ("to_options" in a and (not isinstance(a["to_options"], list) or len(a["to_options"]) < 2)):
                raise rej("an options list needs at least two values", "schema")
            for v in vals:
                if not isinstance(v, str) or not self.spec.value_ok(f, v):
                    raise rej(f"value {v!r} not in the domain of {f}", "value")
            if r["type"] == "correction":
                tgt = next((x for x in prior if x["rid"] == a["target"]), None)
                if tgt is None or tgt["type"] != "state" or not any(b["field"] == f for b in tgt["assertions"]):
                    raise rej(f"correction target {a['target']} did not assert {f}", "correction_target")

    def ingest(self, report):
        self._validate(report)
        self.log.append("report", report)
        return self.log.version

    def record_unprocessed(self, rid, received_at, raw_text, candidate, code, message):
        fields = self.spec.fields_named_in(raw_text)
        body = {"rid": rid, "received_at": received_at, "raw": raw_text, "candidate": candidate, "code": code,
                "message": message, "affected_fields": fields, "context_wide": not fields}
        self.log.append("pending", body)
        return body

    # ---------------------------------------------------------------- views
    def view(self, kind, t, cutoff=None):
        if kind == "earlier":
            reps, pend = self.reports(cutoff), self.pending(cutoff)
            key = ("earlier", t, cutoff, E._sha([reps, pend]))
        elif kind in ("current", "retrospective"):
            reps, pend = self.reports(), self.pending()
            key = (kind, t, self.log.version)
        else:
            raise E.EngineError(kind)
        if key in self._cache:
            return copy.deepcopy(self._cache[key])
        fields = []
        for r in reps:
            for a in r["assertions"]:
                if a["field"] not in fields:
                    fields.append(a["field"])
        inc = sorted({f for p in pend for f in p["affected_fields"]})
        ctx = any(p["context_wide"] for p in pend)
        detail, per = {}, {}
        for f in fields:
            d = resolve_field(self.spec.domain_values(f), reps, f, t)
            detail[f] = d
            if d["status"] == "not_yet_described":
                continue
            per[f] = d["value"] if d["status"] in ("value", "unknown") else "conflict"
        complete = {f: ("incomplete" if (ctx or f in inc) else v) for f, v in per.items()}
        for f in inc:
            complete.setdefault(f, "incomplete")
        choices = []
        sfields = [f for f in per if detail[f]["status"] in ("value", "unknown")]
        for f in sfields:
            d = detail[f]
            choices.append([d["value"]] if d["status"] == "value" else d["options"])
        fixed = {"agent.at": self.spec.agent_at} if self.spec.domain == "delivery" else {}
        states = [dict(dict(zip(sfields, c)), **fixed) for c in itertools.product(*choices)]
        v = {"per_field": per, "complete_per_field": complete, "detail": detail, "states": states,
             "incomplete_fields": inc, "context_incomplete": ctx,
             "conflict_fields": sorted(f for f in per if per[f] == "conflict"), "pending": [p["rid"] for p in pend],
             "not_yet_described": [f for f in fields if detail[f]["status"] == "not_yet_described"]}
        self._cache[key] = v
        return copy.deepcopy(v)

    # ---------------------------------------------------------------- actions
    def branch(self, t, kind="current", cutoff=None):
        v = self.view(kind, t, cutoff)
        b = E.Branch(v["states"], self.log.version, incomplete=v["incomplete_fields"],
                     context_incomplete=v["context_incomplete"])
        b.conflicts = v["conflict_fields"]
        return b

    def check_action(self, branch, action):
        """As v0.2, plus: a verdict that depends on a conflicted field is "unresolved_conflict"."""
        conflicts = getattr(branch, "conflicts", [])
        base = E.Branch(branch.states, branch.base_version, incomplete=branch.incomplete,
                        context_incomplete=branch.context_incomplete)
        out = self.actions.check_action(base, action)
        if conflicts:
            wide = E.Branch(branch.states, branch.base_version, incomplete=sorted(set(branch.incomplete) | set(conflicts)),
                            context_incomplete=branch.context_incomplete)
            w = self.actions.check_action(wide, action)
            if w["verdict"] not in ("allowed", "blocked") and out["verdict"] in ("allowed", "blocked",
                                                                                 "unresolved_pending"):
                out = dict(w, verdict="unresolved_conflict", verdict_ignoring_conflict=out["verdict"])
            else:
                out = dict(w, verdict=w["verdict"])
        return out

    def predict_action(self, branch, action):
        return self.actions.predict_action(branch, action)

    # ---------------------------------------------------------------- persistence
    def save(self, path):
        tmp = f"{path}.tmp"
        with open(tmp, "w") as fh:
            fh.write(json.dumps({"engine": "assertions-0.3", "context": self.log.context, "spec": self.spec.to_json()},
                                sort_keys=True) + "\n")
            for e in self.log.entries:
                fh.write(json.dumps(e, sort_keys=True) + "\n")
            fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        with open(path) as fh:
            lines = fh.read().split("\n")
        if not lines or lines[-1] != "":
            raise E.IncompleteWrite("file does not end with a complete line")
        lines = lines[:-1]
        head = json.loads(lines[0])
        eng = cls(E.WorldSpec(head["spec"]), head["context"])
        for n, line in enumerate(lines[1:], 1):
            try:
                e = json.loads(line)
            except ValueError:
                raise E.IncompleteWrite(f"line {n + 1} incomplete")
            if e.get("seq") != n or e.get("prev") != eng.log.head():
                raise E.IncompleteWrite(f"entry {n} fails the chain")
            if e["type"] == "report":
                eng.ingest(e["body"])
            elif e["type"] == "pending":
                eng.log.append("pending", e["body"])
            else:
                raise E.IncompleteWrite(f"entry {n} unknown type")
            if eng.log.entries[-1]["sha"] != e["sha"]:
                raise E.IncompleteWrite(f"entry {n} does not replay to the same hash")
        return eng
