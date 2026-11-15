"""V1.19.0 declared 4-bit inference protocol (QLOAD-NF4-v1). The V1.1 loader (modeling.load_local_model) is unchanged
and still refuses quantized checkpoints; this separately tested path loads an unquantized publisher checkpoint with
bitsandbytes NF4 at load time, for inference only (no adapters, no optimisation steps).

Recipe (identical for every model in a comparison): bitsandbytes NF4, double quantization, BF16 compute and BF16
non-quantized modules, the whole model on one CUDA device (device_map {"": 0}; no CPU or disk offload: any module
off the GPU is an error), low_cpu_mem_usage streaming, attention "sdpa", eval mode, no gradients. The publisher chat
template with thinking disabled is applied by modeling.render_chat (unchanged). Peak host RSS and GPU memory are
recorded."""
import os
import resource
import time

from .modeling import verify_local_manifest

PROTOCOL = "QLOAD-NF4-v1"


def load_local_model_nf4(cfg):
    t0 = time.time()
    manifest = verify_local_manifest(cfg)
    t_hash = time.time() - t0
    import json
    from pathlib import Path
    if json.loads((Path(cfg["path"]) / "config.json").read_text()).get("quantization_config"):
        raise ValueError("pre-quantized checkpoints are outside QLOAD-NF4-v1")
    for k, v in (("HF_HUB_OFFLINE", "1"), ("TRANSFORMERS_OFFLINE", "1"), ("HF_HUB_DISABLE_TELEMETRY", "1")):
        os.environ[k] = v
    import torch
    import bitsandbytes
    import transformers
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    if cfg.get("quantization") != "nf4" or cfg.get("device") != "cuda" or cfg.get("dtype") != "bfloat16":
        raise ValueError("QLOAD-NF4-v1 requires quantization nf4, device cuda, dtype bfloat16")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    tok = AutoTokenizer.from_pretrained(cfg["path"], local_files_only=True, trust_remote_code=False)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    if "enable_thinking" in cfg:
        tok.dream_chat_kwargs = {"enable_thinking": bool(cfg["enable_thinking"])}
    q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True,
                           bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_quant_storage=torch.uint8)
    torch.cuda.reset_peak_memory_stats()
    t1 = time.time()
    model = AutoModelForCausalLM.from_pretrained(cfg["path"], local_files_only=True, trust_remote_code=False,
                                                 use_safetensors=True, quantization_config=q, torch_dtype=torch.bfloat16,
                                                 device_map={"": 0}, low_cpu_mem_usage=True, attn_implementation="sdpa")
    t_load = time.time() - t1
    devs = {str(p.device) for p in model.parameters()} | {str(b.device) for b in model.buffers()}
    if any(not d.startswith("cuda") for d in devs):
        raise RuntimeError(f"modules off the GPU: {sorted(devs)}")
    if getattr(model, "hf_device_map", None) and any(v not in (0, "cuda:0", "cuda") for v in model.hf_device_map.values()):
        raise RuntimeError(f"offload in device map: {model.hf_device_map}")
    for p in model.parameters():
        p.requires_grad_(False)
    model.eval()
    info = {"protocol": PROTOCOL, "hash_verify_s": round(t_hash, 1), "load_s": round(t_load, 1),
            "peak_host_rss_gib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 2 ** 20, 2),
            "gpu_allocated_after_load_gib": round(torch.cuda.memory_allocated() / 2 ** 30, 2),
            "gpu_peak_load_gib": round(torch.cuda.max_memory_allocated() / 2 ** 30, 2),
            "devices": sorted(devs), "torch": torch.__version__, "cuda": torch.version.cuda,
            "transformers": transformers.__version__, "bitsandbytes": bitsandbytes.__version__,
            "driver": _driver(), "attn_implementation": "sdpa",
            "quantization": {"load_in_4bit": True, "bnb_4bit_quant_type": "nf4", "bnb_4bit_use_double_quant": True,
                             "bnb_4bit_compute_dtype": "bfloat16", "non_quantized_dtype": "bfloat16"}}
    return model, tok, manifest, info


def _driver():
    try:
        import subprocess
        return subprocess.run(["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"], capture_output=True,
                              text=True).stdout.strip()
    except Exception:
        return None
