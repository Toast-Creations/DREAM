"""V1.14.0 panel: 24 new base worlds (12 per domain) built with the unchanged 1.12.0 row builder (tempo.freshgen.build)
from a NEW allocation designed for observation coverage: paired goals whose prerequisites compete for the spare
query capacity, plus predeclared controls. Declarations are rewritten to the fixed public window (12, 14) exactly
as in 1.13.0 (tempo.timinggen.build).

freshgen.py and timinggen.py are byte-unchanged; the two new pool names are registered in freshgen's consonant table
at import time (the table is data; this is the only runtime addition).

Row format (freshgen): delivery (id, A crate (truth, status), B crate (truth, status), transitions
[(crate, from, to)], tape [(transition index, elapsed)], labels); assembly (id, A {T, G}, B {S2, D}, transitions,
tape, labels). Status "ver" = verified (P2 does not query it), "prov" = provisional (P2 queries it), "unres:X" =
unresolved (P2 queries it). Labels are the intended construction (hidden; scoring/reporting only, never an input).

Construction notes (public mechanics; the selector itself only sees reports, declarations and the dependency table):
  * delivery competition: both crates verified, one possible move each (Q0 empty for both goals; each goal's
    dependency set names its own crate; the random pool also holds the other goal's crate).
  * delivery mixed: one goal's crate provisional/unresolved (in that goal's Q0), the other verified but movable.
  * assembly competition: one goal's provisional field covered by Q0 plus a verified prerequisite that can change;
    the other goal's changeable fact competes for the spare query.
  * joint effects (a04): return-to-stock; Q0's late stock reading already determines the slot (redundant check).
  * controls: uncertainty confined to the other goal, plan guaranteed despite uncertainty elsewhere, singleton random
    pools, full Q0 (no spare capacity), menu-coverage gaps, a genuinely infeasible goal.
"""
from . import freshgen as FG, timing as TM

POOLS = {"depq": "fjknrsw", "depqsmoke": "bdhlmvz"}
FG.CONS.update(POOLS)

DELIVERY = [
    ("d01", ("B", "ver"), ("YOU", "ver"), [("EA", "B", "YOU"), ("EB", "YOU", "B")], [(0, 0.5)],
     ("compete_gain_realized", "compete_no_change")),
    ("d02", ("YOU", "ver"), ("B", "ver"), [("EA", "YOU", "B"), ("EB", "B", "C")], [],
     ("compete_no_change", "compete_gap_possible_no_change")),
    ("d03", ("B", "ver"), ("B", "ver"), [("EA", "B", "C"), ("EB", "B", "YOU")], [(0, 1.5), (1, 0.5)],
     ("compete_menu_gap_realized", "compete_gain_realized")),
    ("d04", ("C", "ver"), ("YOU", "ver"), [("EA", "C", "B"), ("EB", "YOU", "G")], [(1, 1.5)],
     ("compete_gap_open_no_change", "compete_done_by_other_realized")),
    ("d05", ("B", "ver"), ("C", "ver"), [("EA", "B", "G"), ("EB", "C", "YOU")], [(0, 0.5), (1, 1.5)],
     ("compete_done_by_other_realized", "compete_gap_open_realized")),
    ("d06", ("YOU", "ver"), ("B", "ver"), [("EA", "YOU", "B"), ("EB", "B", "G"), ("Z", "ZV", "ZO")], [(2, 0.5)],
     ("compete_pool3_no_change", "compete_pool3_no_change")),
    ("d07", ("B", "prov"), ("YOU", "ver"), [("EB", "YOU", "B"), ("EA", "B", "YOU")], [(0, 0.5)],
     ("covered_other_goal_uncertain", "mixed_realized")),
    ("d08", ("YOU", "unres:B"), ("B", "ver"), [("EB", "B", "YOU")], [(0, 1.5)],
     ("covered_other_goal_uncertain", "mixed_unresolved_competitor_realized")),
    ("d09", ("B", "ver"), ("G", "ver"), [("EA", "B", "C")], [],
     ("singleton_pool", "guaranteed_despite_uncertainty_elsewhere")),
    ("d10", ("YOU", "prov"), ("B", "prov"), [("Z", "ZV", "ZO")], [(0, 0.5)],
     ("other_entity_only", "other_entity_only")),
    ("d11", ("C", "ver"), ("B", "unres:C"), [("EA", "C", "YOU")], [],
     ("menu_gap_no_change", "covered_other_goal_uncertain")),
    ("d12", ("YOU", "ver"), ("C", "prov"), [("EA", "YOU", "C"), ("EB", "C", "B")], [(0, 0.5), (1, 1.5)],
     ("compete_menu_gap_realized", "covered_other_goal_uncertain")),
]

ASSEMBLY = [
    ("a01", {"T": ("empty", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
     [("on_hand", "G", "yes", "no"), ("on_hand", "D", "yes", "no")], [(0, 0.5)],
     ("q0_plus_stock_loss_realized", "compete_no_change")),
    ("a02", {"T": ("empty", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "prov")},
     [("install", "T", "W"), ("install", "S2", "LO")], [(0, 1.5)],
     ("compete_slot_taken_realized", "q0_plus_slot_no_change")),
    ("a03", {"T": ("W", "ver"), "G": ("yes", "prov")}, {"S2": ("HI", "ver"), "D": ("yes", "ver")},
     [("remove", "T", "W"), ("remove", "S2", "HI")], [(1, 0.5)],
     ("q0_plus_slot_no_change", "compete_removed_realized")),
    ("a04", {"T": ("G", "ver"), "G": ("no", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "ver")},
     [("return", "T", "G"), ("on_hand", "D", "no", "yes")], [(0, 0.5)],
     ("joint_redundant_realized", "compete_pool3_no_change")),
    ("a05", {"T": ("empty", "prov"), "G": ("yes", "prov")}, {"S2": ("empty", "ver"), "D": ("no", "ver")},
     [("on_hand", "D", "no", "yes"), ("install", "T", "W")], [(0, 0.5)],
     ("full_q0_no_capacity", "compete_delivered_realized")),
    ("a06", {"T": ("G", "prov"), "G": ("no", "ver")}, {"S2": ("empty", "prov"), "D": ("no", "ver")},
     [("on_hand", "G", "no", "yes"), ("on_hand", "D", "no", "yes")], [(0, 0.5), (1, 1.5)],
     ("q0_plus_stock_gain_realized", "q0_plus_stock_gain_realized")),
    ("a07", {"T": ("empty", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("no", "ver")},
     [("on_hand", "G", "yes", "no"), ("install", "T", "W"), ("install", "S2", "LO")], [(1, 0.5)],
     ("two_additions_pool3_realized", "infeasible_goal")),
    ("a08", {"T": ("W", "prov"), "G": ("yes", "ver")}, {"S2": ("LO", "unres:HI"), "D": ("yes", "prov")},
     [("remove", "T", "W")], [(0, 1.5)],
     ("covered_other_goal_uncertain", "full_q0_no_capacity")),
    ("a09", {"T": ("empty", "ver"), "G": ("no", "prov")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
     [("install", "T", "W")], [],
     ("singleton_pool", "covered_other_goal_uncertain")),
    ("a10", {"T": ("W", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
     [("on_hand", "G", "yes", "no"), ("install", "S2", "HI")], [(0, 0.5)],
     ("compete_menu_gap_realized", "compete_no_change")),
    ("a11", {"T": ("empty", "unres:W"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
     [("on_hand", "D", "yes", "no"), ("on_hand", "G", "yes", "no")], [(1, 1.5)],
     ("q0_plus_stock_loss_realized", "compete_pool3_no_change")),
    ("a12", {"T": ("empty", "ver"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
     [("install", "T", "W"), ("install", "S2", "LO"), ("on_hand", "D", "yes", "no")], [(0, 0.5), (2, 1.5)],
     ("compete_pool3_realized", "two_additions_pool3_realized")),
]

SMOKE_D = [("s-d1", ("B", "ver"), ("YOU", "prov"), [("EA", "B", "YOU"), ("EB", "YOU", "B")], [(0, 1.5)],
            ("smoke", "smoke")),
           ("s-d2", ("C", "ver"), ("B", "ver"), [("EA", "C", "B")], [], ("smoke", "smoke"))]
SMOKE_A = [("s-a1", {"T": ("empty", "prov"), "G": ("yes", "ver")}, {"S2": ("empty", "ver"), "D": ("yes", "ver")},
            [("on_hand", "G", "yes", "no"), ("install", "S2", "LO")], [(1, 0.5)], ("smoke", "smoke")),
           ("s-a2", {"T": ("G", "ver"), "G": ("no", "ver")}, {"S2": ("HI", "prov"), "D": ("no", "ver")},
            [("return", "T", "G")], [], ("smoke", "smoke"))]

ROWS = [("delivery", r) for r in DELIVERY] + [("assembly", r) for r in ASSEMBLY]
SMOKE_ROWS = [("delivery", r) for r in SMOKE_D] + [("assembly", r) for r in SMOKE_A]


def build(row, domain, seed, pool):
    w, pub, hid = FG.build(row, domain, seed, pool)
    pub["transitions"] = TM.fixed_windows(pub["transitions"])
    return w, pub, hid


def specs(pool, base_seed, smoke=False):
    import hashlib
    out = []
    for domain, r in (SMOKE_ROWS if smoke else ROWS):
        out.append((domain, r, int(hashlib.sha256(f"{base_seed}|{pool}|{r[0]}".encode()).hexdigest()[:12], 16)))
    return out


goal_copy = FG.goal_copy
