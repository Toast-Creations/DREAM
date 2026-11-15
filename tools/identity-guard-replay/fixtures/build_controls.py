"""Build the public-only control fixtures (invented names; frozen record grammar). No expected labels here:
expected dispositions live in controls-expected.json, written separately and never read by the guard."""
import json
from pathlib import Path


def J(rid, recv, events=(), states=(), revisions=()):
    return json.dumps({"rid": rid, "status": "verified", "received_at": recv, "events": list(events),
                       "states": list(states), "revisions": list(revisions), "evidence": "fixture"})


def ev(f, at, frm="no", to="yes"):
    return {"field": f, "at": at, "from": frm, "to": to}


def st(f, at, v="yes"):
    return {"field": f, "at": at, "value": v}


def rv(target, f, v, start):
    return {"target": target, "field": f, "value": v, "valid_from": start, "valid_to": None}


E = lambda rid, text: {"record_id": rid, "raw_text": text}

# World H: historical occupant. Slot Hokamu held Bakefo at time 3; Cudime replaced it at time 5.
H_PREFIX = [
    E("r01", "Message r01, received at time 3: it is verified that at time 3 another technician fitted part Bakefo into slot Hokamu, using their own stock."),
    E("r02", "Message r02, received at time 4: a confirmed check shows that at time 4 you do not have part Bakefo on hand."),
    E("r03", "Message r03, received at time 5: confirmed (verified) event: at time 5, another technician swapped part Bakefo in slot Hokamu for part Cudime, taking Bakefo away."),
    E("r04", "Message r04, received at time 6: someone verified that, as of time 6, you do not have part Cudime on hand."),
]
H_TARGET = "r05 (came in at time 10): it is verified that at time 10 the part that slot Hokamu held at time 3 went from not on hand to on hand: it was delivered to you."
H_REG = {"Hokamu.part": ["empty", "Bakefo", "Cudime"], "Bakefo.on_hand": ["yes", "no"],
         "Cudime.on_hand": ["yes", "no"], "Dajofe.on_hand": ["yes", "no"]}
H_ORDER = ["Hokamu.part", "Cudime.on_hand", "Dajofe.on_hand", "Bakefo.on_hand"]

# World C: correction of a provisional stock report about the historical occupant.
C_PREFIX = H_PREFIX[:3] + [
    E("r04", "At time 6 we received r04. An early, unconfirmed (provisional) report says that at time 6 you have part Bakefo on hand. It has not been verified yet."),
    E("r05", "r05 (came in at time 7): a confirmed check shows that at time 7 part Cudime is not on hand."),
]
C_TARGET = ("r06 (came in at time 12): this is a verified correction of r04. r04 got whether the part that slot Hokamu "
            "held at time 3 was on hand wrong: actually, from time 6 on, it was not on hand. Nothing physically changed "
            "when this correction arrived.")

# World T: two-hop link.
T_PREFIX = [
    E("r01", "Message r01, received at time 2: checked and confirmed (verified): at time 2, you do not have part Fenogi on hand."),
    E("r02", "At time 3 we received r02. Someone verified that, as of time 3, part Gikabu is not on hand."),
    E("r03", "Message r03, received at time 4: it is verified that at time 4 the part whose stock was checked in r01 is not on hand."),
]
T_TARGET = "r04 (came in at time 8): it is verified that at time 8 the part described in r03 was delivered to you, so it is now on hand."
T_REG = {"Lomaje.part": ["empty", "Pitule"], "Fenogi.on_hand": ["yes", "no"], "Gikabu.on_hand": ["yes", "no"]}
T_ORDER = list(T_REG)

B, Cu = "Bakefo.on_hand", "Cudime.on_hand"
GOOD_H = J("r05", 10, events=[ev(B, 10)])


def H(name, raw, prefix=H_PREFIX, target=H_TARGET, reg=H_REG, order=H_ORDER):
    return {"name": name, "prefix": prefix, "target_text": target, "registry": reg, "registry_order": order, "raw": raw}


CONTROLS = [
    # supported matches
    H("match_event", GOOD_H),
    H("match_state", J("r05", 10, states=[st(B, 10)])),
    H("match_event_plus_redundant_state", J("r05", 10, events=[ev(B, 10)], states=[st(B, 10)])),
    H("match_revision", J("r06", 12, revisions=[rv("r04", B, "no", 6)]), prefix=C_PREFIX, target=C_TARGET),
    {"name": "match_two_hop_event", "prefix": T_PREFIX, "target_text": T_TARGET, "registry": T_REG,
     "registry_order": T_ORDER, "raw": J("r04", 8, events=[ev("Fenogi.on_hand", 8)])},
    # supported mismatches
    H("wrong_registered_subject_event", J("r05", 10, events=[ev(Cu, 10)])),
    H("wrong_registered_subject_revision", J("r06", 12, revisions=[rv("r04", Cu, "no", 6)]), prefix=C_PREFIX,
      target=C_TARGET),
    {"name": "wrong_registered_subject_two_hop", "prefix": T_PREFIX, "target_text": T_TARGET, "registry": T_REG,
     "registry_order": T_ORDER, "raw": J("r04", 8, events=[ev("Gikabu.on_hand", 8)])},
    H("extra_wrong_subject_multi_field", J("r05", 10, states=[st(B, 10), st(Cu, 10, "no")])),
    # identity-only limits: matching subject, wrong value / time -> passes (NOT caught by this check)
    H("matching_subject_wrong_time_not_caught", J("r05", 10, events=[ev(B, 3)])),
    H("matching_subject_wrong_value_not_caught", J("r05", 10, events=[ev(B, 10, "yes", "no")])),
    # compiler rejections stay rejected
    H("malformed_reply", '{"rid": "r05", "events": [ '),
    H("empty_reply_lists", J("r05", 10)),
    H("no_reply", None),
    H("unregistered_field_in_reply", J("r05", 10, events=[ev("Zizozu.on_hand", 10)])),
    # refusals: the matching reply GOOD_H must still not pass
    H("duplicate_envelope", GOOD_H, prefix=H_PREFIX[:2] + [H_PREFIX[1]] + H_PREFIX[2:]),
    {"name": "missing_referenced_envelope", "prefix": T_PREFIX[:2], "target_text": T_TARGET, "registry": T_REG,
     "registry_order": T_ORDER, "raw": J("r04", 8, events=[ev("Fenogi.on_hand", 8)])},
    H("conflicting_historical_support", GOOD_H, prefix=H_PREFIX[:3] + [
        E("r04", "Message r04, received at time 6: checked and confirmed (verified): at time 4, slot Hokamu holds part Cudime.")]),
    H("relevant_unsupported_wording", GOOD_H, prefix=H_PREFIX[:3] + [
        E("r04", "Message r04, received at time 6: a provisional report, not yet verified, states that as of time 6 slot Hokamu is empty.")]),
    H("unresolved_reference_no_support", GOOD_H, target=H_TARGET.replace("held at time 3", "held at time 2")),
    H("unregistered_resolved_field", GOOD_H, reg={k: v for k, v in H_REG.items() if k != B},
      order=[k for k in H_ORDER if k != B]),
    H("literal_only", GOOD_H, target=H_TARGET.replace("the part that slot Hokamu held at time 3", "part Bakefo")),
    H("multiple_descriptions", GOOD_H, target=H_TARGET.replace(
        "went from", "and the part described in r02 went from")),
    H("no_entity", GOOD_H, target="r05 (came in at time 10): it is verified that at time 10 something was delivered to you."),
]


if __name__ == "__main__":
    out = Path(__file__).with_name("controls-inputs.jsonl")
    out.write_text("".join(json.dumps(c, sort_keys=True) + "\n" for c in CONTROLS))
    print(out, len(CONTROLS))
