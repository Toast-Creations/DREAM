"""V1.19.0 extraction runner: scripts/tempo_run.py (unchanged: one content attempt per call, per-call atomic records,
LOCK binding to config/calls/source hashes, infrastructure-only retry, committed order) with the model loader swapped
for the declared NF4 protocol (dream_core.modeling_q.load_local_model_nf4). The load record (protocol, versions,
peak host RSS and GPU memory, devices) is written to HUB/stages/STAGE/LOAD.json.
Usage: hold_run.py --hub HUB --stage STAGE --config CONFIG.json [--fake REPLIES.json]"""
import json
import sys
from pathlib import Path

import tempo_run as TR


class QModel(TR.HFModel):
    def __init__(self, cfg):
        import torch
        from dream_core.modeling_q import load_local_model_nf4
        self.torch = torch
        self.model, self.tok, self.manifest, self.load_info = load_local_model_nf4(cfg)
        eos = self.model.generation_config.eos_token_id
        self.eos = set(eos if isinstance(eos, list) else [eos]) | {self.tok.eos_token_id}
        import transformers
        self.identity = {"revision": self.manifest.get("revision"), "path": cfg["path"], "dtype": cfg["dtype"],
                         "quantization": "nf4", "enable_thinking": cfg["enable_thinking"], "decoding": "greedy",
                         "torch": torch.__version__, "transformers": transformers.__version__, "load": self.load_info}
        a = sys.argv
        hub, stage = Path(a[a.index("--hub") + 1]), a[a.index("--stage") + 1]
        (hub / "stages" / stage).mkdir(parents=True, exist_ok=True)
        (hub / "stages" / stage / "LOAD.json").write_text(json.dumps(self.identity, indent=1))


if __name__ == "__main__":
    if "--fake" not in sys.argv:
        TR.HFModel = QModel
    TR.main()
