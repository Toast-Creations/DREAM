"""Temporal state engine v0.1 (DREAM 1.8.0). Deterministic infrastructure, not a learned capability.

It guarantees consistency with the evidence it was given and the explicit rules below. It does not guarantee that
the evidence is right: a wrongly extracted record yields a wrong supported state, and the engine will then
faithfully authorise or block actions relative to that wrong state.

Pieces:
  WorldSpec    fixed facts of one episode (places/roads/agent or slots/parts/prices/adapters), from public text.
  EvidenceLog  append-only, versioned, hash-chained log of typed public records, in reception order, one context.
  Engine       supported-state views (current / retrospective / earlier-information), explicit action
               definitions, check/predict on branch copies, and commits of observations and execution outcomes.
  Branch       a hypothetical copy: a set of compatible joint states. Never touches the log.

Supported state comes from two independent public-record resolvers (tempo.resolve, rule timeline; tempo.enumcheck,
trajectory enumeration); the engine raises if they disagree. Alternatives are explicit joint states, so a branch
keeps correlations created by an action (e.g. "X carried and hands full" vs "X elsewhere and hands empty").
The record language constrains fields one at a time, so the initial supported set is the product of the per-field
supported values.

Public record schema (anything else, including scorer or simulator keys, is rejected):
  rid str (unique in the context), kind in KINDS, status in {verified, provisional}, event_at int|None
  (None only for corrections), received_at int (non-decreasing in ingest order), payload (per kind, below),
  optional source str and evidence str (e.g. "env", "extractor:<model>", quoted span).
  initial          {"assign": {field: value}}
  observation      {"field", "value"}
  change           {"field", "from", "to"}
  uncertain_change {"field", "from", "options": [v1, v2, ...]}
  correction       {"target": rid, "field", "value", "valid_from": int, "valid_to": None}
"""
import copy
import hashlib
import itertools
import json
import os
import re

from . import enumcheck, resolve

ENGINE_VERSION = "0.2"
UNKNOWN = "unknown"
CARRIED = "carried by you"
EMPTY = "empty"
YES, NO = "yes", "no"
KINDS = ("initial", "observation", "change", "uncertain_change", "correction")
STATUSES = ("verified", "provisional")
RECORD_KEYS = {"rid", "kind", "status", "event_at", "received_at", "payload", "source", "evidence"}
PAYLOAD_KEYS = {"initial": {"assign"}, "observation": {"field", "value"}, "change": {"field", "from", "to"},
                "uncertain_change": {"field", "from", "options"},
                "correction": {"target", "field", "value", "valid_from", "valid_to"}}


class EngineError(Exception):
    pass


class RecordRejected(EngineError):
    """Ordinary input rejection, with an enumerated code (REJECT_CODES). Anything else raised by the engine is an
    internal failure and must not be treated as a rejection."""

    def __init__(self, message, code="schema"):
        super().__init__(message)
        if code not in REJECT_CODES:
            raise ValueError(f"unknown rejection code {code}")
        self.code = code


# v0.2: enumerated input-contract rules (the only triggers a repair policy may use)
REJECT_CODES = {
    "schema": "the record must use exactly the public keys and the payload keys for its kind",
    "kind_status": "kind must be one of the listed kinds and status verified or provisional",
    "time_type": "event_at and received_at must be integers (event_at is null only for a correction)",
    "correction_event_at": "a correction is not an event: its event_at must be null",
    "time_order": "a record cannot be about a time after it was received",
    "reception_order": "records must arrive in reception order",
    "duplicate_rid": "each record ID may be used once",
    "unregistered_field": "fields must be listed entity attributes",
    "value": "values must be among the field's allowed values",
    "correction_target": "a correction must name an earlier record that stated that fact",
    "correction_interval": "a correction holds from valid_from on (valid_to must be null)",
    "inconsistent": "the record must be consistent with the records accepted so far",
    "missing_prior_state": "a change or unrecorded-result event needs an earlier accepted statement of that fact",
}


class IncompleteWrite(EngineError):
    pass


def _sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


# ====================================================================== world spec

class WorldSpec:
    """Fixed facts of one episode. Entity registry: name -> type (crate | part | slot)."""

    def __init__(self, d):
        self.d = copy.deepcopy(d)
        self.domain = d["domain"]
        if self.domain == "delivery":
            self.places = list(d["places"])
            self.roads = [tuple(r) for r in d["roads"]]
            self.closed = [tuple(sorted(r)) for r in d.get("closed", [])]
            self.agent_at = d["agent_at"]
            self.non_portable = set(d.get("non_portable", []))
            self.registry = {c: "crate" for c in d.get("crates", [])}
        elif self.domain == "assembly":
            self.slots = dict(d["slots"])
            self.parts = {p: dict(v) for p, v in d["parts"].items()}
            self.prices = dict(d["prices"])
            self.adapters = dict(d.get("adapters", {}))
            self.fitted = dict(d.get("fitted", {}))
            self.registry = {**{s: "slot" for s in self.slots}, **{p: "part" for p in self.parts},
                             **{p: "part" for p in d.get("extra_parts", [])}}
        else:
            raise EngineError(f"unknown domain {self.domain}")

    def to_json(self):
        return self.d

    def field_ok(self, field):
        ent, _, attr = field.partition(".")
        want = {"crate": "location", "part": "on_hand", "slot": "part"}.get(self.registry.get(ent))
        return want is not None and attr == want

    ATTR = {"crate": "location", "part": "on_hand", "slot": "part"}

    def domain_values(self, field):
        attr = field.split(".")[1]
        if attr == "location":
            return list(self.places) + [CARRIED]
        if attr == "on_hand":
            return [YES, NO]
        return [EMPTY] + sorted(e for e, t in self.registry.items() if t == "part")

    def fields_named_in(self, text):
        """Registered entity attributes whose entity name occurs in a text (public information only)."""
        return sorted(f"{e}.{self.ATTR[t]}" for e, t in self.registry.items()
                      if re.search(rf"\b{re.escape(e)}\b", text or ""))

    def value_ok(self, field, value):
        ent, attr = field.split(".")
        if attr == "location":
            return value in self.places or value == CARRIED
        if attr == "on_hand":
            return value in (YES, NO)
        if attr == "part":
            return value == EMPTY or self.registry.get(value) == "part"
        return False


# ====================================================================== actions (explicit definitions)

def _actions(spec):
    """name -> (prerequisites [(predicate, fn(state, *args) -> bool)], effect fn(state, *args) -> new state)."""
    if spec.domain == "delivery":
        def carried(s):
            return [f for f, v in s.items() if f.endswith(".location") and v == CARRIED]

        def road(a, b):
            return any({x, y} == {a, b} and a != b for x, y, _ in spec.roads)

        def take_eff(s, x):
            n = dict(s); n[f"{x}.location"] = CARRIED; return n

        def go_eff(s, a, b):
            n = dict(s); n["agent.at"] = b; return n

        def put_eff(s, x):
            n = dict(s); n[f"{x}.location"] = s["agent.at"]; return n
        return {
            "take": ([("crate_at_your_place", lambda s, x: s.get(f"{x}.location") == s["agent.at"]),
                      ("hands_empty", lambda s, x: not carried(s)),
                      ("crate_portable", lambda s, x: x not in spec.non_portable)], take_eff),
            "go": ([("agent_at_start", lambda s, a, b: s["agent.at"] == a),
                    ("road_exists", lambda s, a, b: road(a, b)),
                    ("road_open", lambda s, a, b: tuple(sorted((a, b))) not in spec.closed)], go_eff),
            "put": ([("carrying_crate", lambda s, x: s.get(f"{x}.location") == CARRIED)], put_eff),
        }

    def accepts(s, slot):
        a = spec.fitted.get(slot)
        return spec.adapters[a]["from"] if a else spec.slots[slot]

    def installed(s, p):
        return any(s.get(f"{sl}.part") == p for sl in spec.slots)

    def inst_eff(s, p, sl):
        n = dict(s); n[f"{sl}.part"] = p; n[f"{p}.on_hand"] = NO; return n

    def rem_eff(s, sl):
        n = dict(s); n[f"{s[f'{sl}.part']}.on_hand"] = YES; n[f"{sl}.part"] = EMPTY; return n

    def ord_eff(s, p):
        n = dict(s); n[f"{p}.on_hand"] = YES; return n
    return {
        "install": ([("part_on_hand", lambda s, p, sl: s.get(f"{p}.on_hand") == YES),
                     ("slot_empty", lambda s, p, sl: s.get(f"{sl}.part") == EMPTY),
                     ("connector_matches", lambda s, p, sl: spec.parts[p]["type"] == accepts(s, sl))], inst_eff),
        "remove": ([("slot_holds_part", lambda s, sl: s.get(f"{sl}.part", EMPTY) != EMPTY)], rem_eff),
        "order": ([("part_has_price", lambda s, p: p in spec.prices),
                   ("part_not_on_hand", lambda s, p: s.get(f"{p}.on_hand", NO) != YES),
                   ("part_not_installed", lambda s, p: not installed(s, p))], ord_eff),
        "fit": ([("adapter_exists", lambda s, a, sl: a in spec.adapters)], None),  # no adapters in these episodes
    }


def _three(vals):
    vals = set(vals)
    return vals.pop() if len(vals) == 1 else UNKNOWN


# ====================================================================== evidence log

class EvidenceLog:
    """Append-only, hash-chained. seq = reception order (also the resolvers' ordinal)."""

    def __init__(self, context):
        self.context = context
        self.entries = []  # {"seq", "type": "record"|"execution", "body", "prev", "sha"}

    @property
    def version(self):
        return len(self.entries)

    def head(self):
        return self.entries[-1]["sha"] if self.entries else _sha({"context": self.context})

    def append(self, typ, body):
        e = {"seq": len(self.entries) + 1, "type": typ, "body": copy.deepcopy(body), "prev": self.head()}
        e["sha"] = _sha({k: e[k] for k in ("seq", "type", "body", "prev")})
        self.entries.append(e)
        return e

    def records(self, upto_version=None):
        es = self.entries if upto_version is None else self.entries[:upto_version]
        out = []
        for e in es:
            if e["type"] == "record":
                r = copy.deepcopy(e["body"]); r["ordinal"] = e["seq"]
                out.append(r)
        return out

    def executions(self):
        return [e["body"] for e in self.entries if e["type"] == "execution"]


# ====================================================================== branches

class Branch:
    """A hypothetical: compatible joint states plus the actions imagined on it. Does not reference the log."""

    def __init__(self, states, base_version, actions=(), incomplete=(), context_incomplete=False):
        self.states = _dedup(states)
        self.base_version = base_version
        self.actions = list(actions)
        self.incomplete = sorted(incomplete)
        self.context_incomplete = context_incomplete

    def summary(self):
        """Per field: value, "unknown", or (v0.2) "incomplete" where received evidence was not ingested."""
        fields = sorted({f for s in self.states for f in s} | set(self.incomplete))
        out = {f: _three(s.get(f) for s in self.states) for f in fields}
        for f in fields:
            if self.context_incomplete and f != "agent.at" or f in self.incomplete:
                out[f] = "incomplete"
        return out


def _dedup(states):
    seen, out = set(), []
    for s in states:
        k = json.dumps(s, sort_keys=True)
        if k not in seen:
            seen.add(k); out.append(dict(s))
    return out


# ====================================================================== engine

class Engine:
    def __init__(self, spec, context="ctx"):
        self.spec = spec if isinstance(spec, WorldSpec) else WorldSpec(spec)
        self.log = EvidenceLog(context)
        self.acts = _actions(self.spec)
        self._cache = {}

    # ---------------------------------------------------------------- ingest
    def _validate(self, r):
        if not isinstance(r, dict) or set(r) - RECORD_KEYS or not {"rid", "kind", "status", "event_at",
                                                                    "received_at", "payload"} <= set(r):
            raise RecordRejected(f"record keys {sorted(r) if isinstance(r, dict) else r} outside the public schema",
                                 "schema")
        k, p = r["kind"], r["payload"]
        if k not in KINDS or r["status"] not in STATUSES or not isinstance(r["rid"], str):
            raise RecordRejected("bad kind, status or rid", "kind_status")
        if not isinstance(p, dict) or set(p) != PAYLOAD_KEYS[k]:
            raise RecordRejected(f"payload keys for {k}: {sorted(p) if isinstance(p, dict) else p}", "schema")
        isint = lambda x: isinstance(x, int) and not isinstance(x, bool)
        if k == "correction" and r["event_at"] is not None:
            raise RecordRejected("a correction is not an event: event_at must be None", "correction_event_at")
        if not isint(r["received_at"]) or (k != "correction" and not isint(r["event_at"])):
            raise RecordRejected("times must be integers", "time_type")
        if k != "correction" and r["event_at"] > r["received_at"]:
            raise RecordRejected("a record cannot be about a time after it was received", "time_order")
        if k == "initial" and (not isinstance(p["assign"], dict) or not p["assign"]):
            raise RecordRejected("assign must be a non-empty object", "schema")
        if k != "initial" and not isinstance(p["field"], str):
            raise RecordRejected("field must be a string", "schema")
        if k == "uncertain_change" and (not isinstance(p["options"], list) or len(p["options"]) < 2):
            raise RecordRejected("an unrecorded-result event needs at least two possible results", "schema")
        if k == "correction" and (not isinstance(p["target"], str) or not isint(p["valid_from"])):
            raise RecordRejected("correction target must be a record ID and valid_from an integer", "schema")
        prior = self.log.records()
        if any(x["rid"] == r["rid"] for x in prior):
            raise RecordRejected(f"duplicate rid {r['rid']} in context {self.log.context}", "duplicate_rid")
        if prior and r["received_at"] < prior[-1]["received_at"]:
            raise RecordRejected("records must be ingested in reception order", "reception_order")
        fields = list(p["assign"]) if k == "initial" else [p["field"]]
        for f in fields:
            if not isinstance(f, str) or not self.spec.field_ok(f):
                raise RecordRejected(f"field {f} is not a registered entity attribute in this context",
                                     "unregistered_field")
        vals = {"initial": lambda: list(p["assign"].items()), "observation": lambda: [(p["field"], p["value"])],
                "change": lambda: [(p["field"], p["from"]), (p["field"], p["to"])],
                "uncertain_change": lambda: [(p["field"], p["from"])] + [(p["field"], o) for o in p["options"]],
                "correction": lambda: [(p["field"], p["value"])]}[k]()
        for f, v in vals:
            if not isinstance(v, str) or not self.spec.value_ok(f, v):
                raise RecordRejected(f"value {v!r} not allowed for {f}", "value")
        if k == "correction":
            tgt = next((x for x in prior if x["rid"] == p["target"]), None)
            if tgt is None:
                raise RecordRejected(f"correction targets {p['target']}, not a report in context {self.log.context}",
                                     "correction_target")
            asserted = list(tgt["payload"]["assign"]) if tgt["kind"] == "initial" else (
                [tgt["payload"]["field"]] if tgt["kind"] == "observation" else [])
            if p["field"] not in asserted:
                raise RecordRejected("correction names a field its target did not assert", "correction_target")
            if p["valid_to"] is not None:
                raise RecordRejected("bounded correction intervals are not supported", "correction_interval")

    def _check_consistent(self, records):
        new = records[-1]
        if new["kind"] in ("change", "uncertain_change"):
            f = new["payload"]["field"]
            stated = [a for a in resolve._assertions(records[:-1]) if a[0] == f]
            if not stated:  # v0.2: the v0.1 KeyError path, now an explicit rejection
                raise RecordRejected(f"no earlier accepted statement of {f}", "missing_prior_state")
        try:
            for f in resolve.fields_of(records):
                enumcheck.supported(records, f, max(r["received_at"] for r in records))
        except enumcheck.Inconsistent as e:
            raise RecordRejected(f"inconsistent with prior evidence: {e}", "inconsistent")

    def ingest_report(self, record):
        """Record a permitted report with its original provenance/status. Status is never changed afterwards."""
        self._validate(record)
        trial = self.log.records() + [dict(copy.deepcopy(record), ordinal=self.log.version + 1)]
        self._check_consistent(trial)
        self.log.append("record", record)
        return self.log.version

    def apply_correction(self, record):
        """A verified correction: withdraws the target's statement about the field from valid_from; replay is
        implicit (views are recomputed from the log). The original report stays in the log."""
        if record.get("kind") != "correction" or record.get("status") != "verified":
            raise RecordRejected("apply_correction takes a verified correction record", "kind_status")
        return self.ingest_report(record)

    commit_observation = ingest_report  # an observation/outcome reported by the environment

    def record_unprocessed(self, rid, received_at, raw_text, candidate, code, message):
        """v0.2: register received evidence that was not ingested (kept with its raw text, candidate extraction and
        reason). Affected scope = registered entity attributes named in the raw text; if none can be identified, the
        whole context is marked incomplete. The last accepted values stay in the log but are no longer presented
        as fully processed."""
        fields = self.spec.fields_named_in(raw_text)
        body = {"rid": rid, "received_at": received_at, "raw": raw_text, "candidate": candidate, "code": code,
                "message": message, "affected_fields": fields, "context_wide": not fields}
        self.log.append("pending", body)
        return body

    def pending(self, cutoff=None):
        return [e["body"] for e in self.log.entries if e["type"] == "pending"
                and (cutoff is None or e["body"]["received_at"] <= cutoff)]

    # ---------------------------------------------------------------- views
    def fields(self, upto_version=None):
        return resolve.fields_of(self.log.records(upto_version))

    def _view(self, records, t):
        all_fields = resolve.fields_of(records)
        described = {a[0] for a in resolve._assertions(records) if a[1] <= t}
        fields = [f for f in all_fields if f in described]
        per2, states = enumcheck.supported_set(records, fields, t)
        for f in fields:  # resolver 1 must agree with resolver 2
            a = resolve.value_at(records, f, t)
            b = per2[f]
            if a[0] != b[0] or (a[0] == "value" and a[1] != b[1]) or (a[0] == "unknown" and sorted(a[1]) != sorted(b[1])):
                raise EngineError(f"resolver disagreement on {f} at {t}: {a} vs {b}")
        per = {f: (v[1] if v[0] == "value" else UNKNOWN) for f, v in per2.items()}
        opts = {f: sorted(v[1]) for f, v in per2.items() if v[0] == "unknown"}
        fixed = self._fixed_state()
        return {"per_field": per, "options": opts, "states": [dict(s, **fixed) for s in states],
                "not_yet_described": [f for f in all_fields if f not in described]}

    def _fixed_state(self):
        return {"agent.at": self.spec.agent_at} if self.spec.domain == "delivery" else {}

    def view(self, kind, t, cutoff=None):
        """kind: current (all evidence, at t = now), retrospective (all evidence, at an earlier t), earlier
        (only evidence received by `cutoff`, at t). Cached per log version; an earlier view reads only its prefix."""
        if kind == "earlier":
            if cutoff is None:
                raise EngineError("earlier view needs a cutoff")
            recs = [r for r in self.log.records() if r["received_at"] <= cutoff]
            pend = self.pending(cutoff)
            key = ("earlier", t, cutoff, _sha([recs, pend]))
        elif kind in ("current", "retrospective"):
            recs = self.log.records()
            pend = self.pending()
            key = (kind, t, self.log.version)
        else:
            raise EngineError(kind)
        if key not in self._cache:
            v = self._view(recs, t)
            inc = sorted({f for p in pend for f in p["affected_fields"]})
            ctx = any(p["context_wide"] for p in pend)
            v.update(pending=[p["rid"] for p in pend], incomplete_fields=inc, context_incomplete=ctx,
                     complete_per_field={f: ("incomplete" if ctx or f in inc else x)
                                         for f, x in v["per_field"].items()})
            for f in inc:
                v["complete_per_field"].setdefault(f, "incomplete")
            self._cache[key] = v
        return copy.deepcopy(self._cache[key])

    def explain(self, field, t, cutoff=None):
        """Evidence links for one field: every record about it that the view could see, with its role."""
        recs = self.log.records()
        if cutoff is not None:
            recs = [r for r in recs if r["received_at"] <= cutoff]
        withdrawn = {(r["payload"]["target"], r["payload"]["field"]): r["rid"] for r in recs if r["kind"] == "correction"}
        out = []
        for r in recs:
            p = r["payload"]
            about = (field in p["assign"]) if r["kind"] == "initial" else p.get("field") == field
            if not about:
                continue
            role = {"change": "event", "uncertain_change": "event (result not recorded)",
                    "correction": "correction"}.get(r["kind"], "assertion")
            if (r["rid"], field) in withdrawn:
                role = f"withdrawn by {withdrawn[(r['rid'], field)]}"
            out.append({"rid": r["rid"], "kind": r["kind"], "status": r["status"], "event_at": r["event_at"],
                        "received_at": r["received_at"], "role": role, "source": r.get("source")})
        return out

    # ---------------------------------------------------------------- actions
    def _eval(self, state, action):
        name, *args = action
        if name not in self.acts:
            raise EngineError(f"unknown action {name}")
        prereqs, eff = self.acts[name]
        vals = {p: bool(fn(state, *args)) for p, fn in prereqs}
        return vals, all(vals.values()), eff

    def branch(self, t, kind="current", cutoff=None):
        v = self.view(kind, t, cutoff)
        return Branch(v["states"], self.log.version, incomplete=v["incomplete_fields"],
                      context_incomplete=v["context_incomplete"])

    def _widen(self, branch):
        fs = set(branch.incomplete)
        if branch.context_incomplete:
            fs |= {f for s in branch.states for f in s if f != "agent.at"}
        if not fs:
            return branch.states
        fs = sorted(fs)
        out = []
        for s in branch.states:
            for combo in itertools.product(*[self.spec.domain_values(f) for f in fs]):
                out.append(dict(s, **dict(zip(fs, combo))))
        return out

    def check_action(self, branch, action):
        """allowed / blocked / unresolved over the branch's compatible states, with three-valued prerequisites.
        v0.2: fields touched by received-but-unprocessed evidence may hold any value. A verdict that survives that
        widening stands (e.g. blocked by a known-false prerequisite); one that depends on it is
        "unresolved_pending"; alternatives permitted by the ingested evidence alone give "unresolved"."""
        def verdict_of(states):
            per = [self._eval(s, action)[:2] for s in states]
            oks = {ok for _, ok in per}
            return per, ("allowed" if oks == {True} else ("blocked" if oks == {False} else "unresolved"))
        per, verdict = verdict_of(branch.states)
        preds = {p: _three(v[p] for v, _ in per) for p in per[0][0]}
        out = {"action": list(action), "verdict": verdict, "prerequisites": preds,
               "states_allowed": sum(ok for _, ok in per), "states": len(per)}
        if branch.incomplete or branch.context_incomplete:
            wper, wv = verdict_of(self._widen(branch))
            out["verdict_ignoring_pending"] = verdict
            out["prerequisites"] = {p: _three(v[p] for v, _ in wper) for p in wper[0][0]}
            out["verdict"] = wv if wv != "unresolved" else ("unresolved_pending" if verdict != "unresolved"
                                                           else "unresolved")
        return out

    def predict_action(self, branch, action):
        """Declared transition on a copy. Blocked: no effect. Unresolved: each compatible state keeps its own
        outcome, so alternatives (and their correlations) are retained."""
        out = []
        for s in branch.states:
            _, ok, eff = self._eval(s, action)
            out.append(eff(s, *action[1:]) if ok and eff else dict(s))
        return Branch(out, branch.base_version, branch.actions + [list(action)])

    def commit_execution(self, exec_id, action, t, source="execution"):
        """Commit an executed action's outcome. Idempotent per exec_id (a duplicate suggestion never executes
        twice). Allowed: its effects are appended as verified change records. Blocked: recorded as a failed
        attempt with no effect. Unresolved: refused; the outcome must arrive as an observation instead."""
        prior = [e for e in self.log.executions() if e["exec_id"] == exec_id]
        if prior:
            return dict(prior[0], duplicate=True)
        b = self.branch(t)
        chk = self.check_action(b, action)
        if chk["verdict"] in ("unresolved", "unresolved_pending"):
            raise EngineError("execution outcome under unresolved prerequisites: commit an observation instead")
        rids = []
        if chk["verdict"] == "allowed":
            # allowed in every compatible state; the changed fields must change identically in all of them
            changes = set()
            for s in b.states:
                a2 = self.predict_action(Branch([s], b.base_version), action).states[0]
                if a2.get("agent.at") != s.get("agent.at"):
                    raise EngineError("v0.1 keeps the courier's position fixed: moves are predicted, not committed")
                changes.add(tuple(sorted((f, s.get(f), a2[f]) for f in a2 if a2[f] != s.get(f))))
            if len(changes) != 1:
                raise EngineError("effects differ across compatible states: commit an observation of the result")
            delta = {f: (frm, to) for f, frm, to in changes.pop()}
            before = {f: frm for f, (frm, _) in delta.items()}
            after = {f: to for f, (_, to) in delta.items()}
            for n, f in enumerate(sorted(delta)):
                rid = f"{exec_id}:{n}"
                self.ingest_report({"rid": rid, "kind": "change", "status": "verified", "event_at": t,
                                    "received_at": t, "payload": {"field": f, "from": before[f], "to": after[f]},
                                    "source": f"{source}:{exec_id}"})
                rids.append(rid)
        body = {"exec_id": exec_id, "action": list(action), "t": t, "verdict": chk["verdict"], "records": rids}
        self.log.append("execution", body)
        return dict(body, duplicate=False)

    # ---------------------------------------------------------------- persistence
    def save(self, path):
        """Whole-file atomic write: header line then one line per log entry (hash-chained)."""
        tmp = f"{path}.tmp"
        with open(tmp, "w") as fh:
            fh.write(json.dumps({"engine": ENGINE_VERSION, "context": self.log.context,
                                 "spec": self.spec.to_json()}, sort_keys=True) + "\n")
            for e in self.log.entries:
                fh.write(json.dumps(e, sort_keys=True) + "\n")
            fh.flush(); os.fsync(fh.fileno())
        os.replace(tmp, path)

    def append_to(self, path, entry):
        with open(path, "a") as fh:
            fh.write(json.dumps(entry, sort_keys=True) + "\n")
            fh.flush(); os.fsync(fh.fileno())

    @classmethod
    def load(cls, path):
        """Verify every line, the hash chain and the sequence. A partial or corrupted line raises IncompleteWrite:
        an incomplete write can never be read back as a committed event."""
        with open(path) as fh:
            lines = fh.read().split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        else:
            raise IncompleteWrite("file does not end with a complete line")
        try:
            head = json.loads(lines[0])
        except (ValueError, IndexError):
            raise IncompleteWrite("bad header")
        eng = cls(WorldSpec(head["spec"]), head["context"])
        for n, line in enumerate(lines[1:], 1):
            try:
                e = json.loads(line)
            except ValueError:
                raise IncompleteWrite(f"line {n + 1} is not a complete entry")
            if e.get("seq") != n or e.get("prev") != eng.log.head() or \
                    e.get("sha") != _sha({k: e.get(k) for k in ("seq", "type", "body", "prev")}):
                raise IncompleteWrite(f"entry {n} fails the hash chain")
            if e["type"] == "record":
                eng.ingest_report(e["body"])  # replay through full validation
            elif e["type"] in ("execution", "pending"):
                eng.log.append(e["type"], e["body"])
            else:
                raise IncompleteWrite(f"entry {n} has unknown type {e['type']}")
            if eng.log.entries[-1]["sha"] != e["sha"]:
                raise IncompleteWrite(f"entry {n} does not replay to the same hash")
        return eng


# ====================================================================== model-output audit

def audit_model_action(engine, t, action, raw_text, parsed=None):
    """Keep three things separate: the raw model reply, the engine's decision, and the engine's successor.
    `parsed` is the scorer's parse of the reply (applicability and predicted fields), if any."""
    b = engine.branch(t)
    chk = engine.check_action(b, action)
    succ = engine.predict_action(b, action)
    out = {"raw": raw_text, "model": parsed, "engine_check": chk, "engine_successor": succ.summary(),
           "log_version_unchanged": engine.log.version == b.base_version}
    if parsed is not None:
        mp = parsed.get("predicted") or {}
        out["model_applicable"] = parsed.get("applicable")
        out["successor_differs"] = any(mp.get(f) is not None and mp.get(f) != v
                                       for f, v in out["engine_successor"].items() if f in mp)
    return out
