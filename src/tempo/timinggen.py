"""V1.13.0 panel: 24 new base worlds with the 1.12.0 kinds of change (tempo.freshgen.DELIVERY / ASSEMBLY rows,
unchanged), new pools and seeds, and declarations rewritten to the fixed public activity window (12, 14).

freshgen.py is byte-unchanged; the two new pool names are registered in its consonant table at import time
(the table is data; this is the only runtime addition)."""
from . import freshgen as FG, timing as TM

POOLS = {"timing": "dfhmnsv", "timingsmoke": "bcjlprt"}
FG.CONS.update(POOLS)

ROWS = [("delivery", r) for r in FG.DELIVERY] + [("assembly", r) for r in FG.ASSEMBLY]
SMOKE_ROWS = [("delivery", r) for r in FG.SMOKE_D] + [("assembly", r) for r in FG.SMOKE_A]


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
