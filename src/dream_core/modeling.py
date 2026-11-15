"""Local-only model loading. Optional ML dependencies are imported lazily."""
import json
import os
from pathlib import Path
import re
from .ledger import file_hash


def verify_local_manifest(cfg):
    if not cfg.get("path") or not cfg.get("manifest"):
        raise ValueError("Set a trusted local model directory and model manifest first")
    root = Path(cfg["path"]).resolve()
    manifest_path = Path(cfg["manifest"]).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not re.fullmatch(r"[a-fA-F0-9]{40}", manifest.get("revision", "")):
        raise ValueError("Manifest requires the actual immutable model commit ID")
    if not manifest.get("model_id") or not manifest.get("files"):
        raise ValueError("Model identity and content hashes are required")
    listed = set()
    for item in manifest["files"]:
        path = (root / item["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file() or path in listed:
            raise ValueError("Invalid, duplicate, or escaping manifest path")
        listed.add(path)
        if file_hash(path) != item["sha256"]:
            raise ValueError("Model content hash mismatch: " + item["path"])
    required = {p.resolve() for p in root.rglob("*") if p.is_file() and
                (p.suffix in (".safetensors", ".json", ".model", ".txt", ".jinja") and
                 p.resolve() != manifest_path)}
    if not required.issubset(listed) or not any(p.suffix == ".safetensors" for p in listed):
        raise ValueError("Manifest must cover all loader data and safetensors weights")
    return manifest


def load_local_model(cfg):
    manifest = verify_local_manifest(cfg)
    model_config = json.loads((Path(cfg["path"])/"config.json").read_text(encoding="utf-8"))
    if model_config.get("quantization_config"):
        raise ValueError("Quantized checkpoints require a separately tested protocol; V1.1 refuses implicit quantization")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    device = cfg.get("device", "cuda")
    dtype_name = cfg.get("dtype", "bfloat16")
    if device not in ("cpu", "cuda") or dtype_name not in ("float32", "bfloat16"):
        raise ValueError("V1.1 supports one CPU/CUDA device and FP32 or BF16")
    if device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    if dtype_name == "bfloat16" and (device != "cuda" or not torch.cuda.is_bf16_supported()):
        raise ValueError("BF16 requires a supported CUDA device; choose CPU FP32 for wiring tests")
    options = dict(local_files_only=True, trust_remote_code=False)
    if cfg.get("tokenizer_loader", "auto") == "fast_json":
        # V1.4.0: load the publisher's tokenizer.json directly. Mistral-7B-Instruct-v0.3 declares
        # LlamaTokenizer with add_prefix_space=True, which makes AutoTokenizer demand the slow
        # sentencepiece/protobuf path; the fast tokenizer file is the publisher's own serialization.
        from transformers import PreTrainedTokenizerFast
        tokenizer = PreTrainedTokenizerFast.from_pretrained(cfg["path"], **options)
    elif cfg.get("tokenizer_loader", "auto") == "auto":
        tokenizer = AutoTokenizer.from_pretrained(cfg["path"], **options)
    else:
        raise ValueError("model.tokenizer_loader must be auto or fast_json")
    if tokenizer.eos_token_id is None:
        raise ValueError("Model must define an EOS token")
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    # Hybrid reasoning models (Qwen3) take an explicit thinking switch through their
    # chat template. Absent from the config, rendering is unchanged.
    if "enable_thinking" in cfg:
        if not isinstance(cfg["enable_thinking"], bool):
            raise ValueError("model.enable_thinking must be true or false")
        tokenizer.dream_chat_kwargs = {"enable_thinking": cfg["enable_thinking"]}
    # CUDA weights stream straight onto the single GPU so host RAM never holds the
    # whole model. The {"": device} map pins every module to it: no sharding or CPU offload.
    if device == "cuda":
        options.update(device_map={"": device}, low_cpu_mem_usage=True)
    model = AutoModelForCausalLM.from_pretrained(cfg["path"], use_safetensors=True,
                torch_dtype=getattr(torch, dtype_name), **options)
    if device == "cpu":
        model = model.to(device)
    if any(parameter.device.type != device for parameter in model.parameters()):
        raise RuntimeError("Model parameters were not all placed on the requested device")
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    model.eval()
    return model, tokenizer, manifest


def render_chat(tokenizer, text, system=None, *, enable_thinking=None):
    """Render one chat turn. ``enable_thinking`` overrides the loaded switch for this call only.

    V1.3.3: DREAM 2 concept training renders with thinking off, so a direct text
    target follows Qwen3's empty think block instead of competing with "<think>".
    A tokenizer loaded without the switch (not a hybrid reasoning model) ignores it.
    """
    if not getattr(tokenizer, "chat_template", None):
        raise ValueError("Use an instruction model with a documented chat template")
    messages = ([{"role": "system", "content": system}] if system else [])
    messages.append({"role": "user", "content": text})
    kwargs = dict(getattr(tokenizer, "dream_chat_kwargs", {}))
    if enable_thinking is not None and "enable_thinking" in kwargs:
        kwargs["enable_thinking"] = enable_thinking
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, **kwargs)


def split_thinking(text, thinking_enabled, *, ended_with_eos=False):
    """Separate a reasoning block from the answer that scoring and later stages see.

    Reasoning is preserved in the record, never dropped. With thinking enabled, output
    that stops before the closing tag has no answer and is marked truncated.
    """
    if "</think>" in text:
        thinking, _, answer = text.rpartition("</think>")
        return {"text": answer.strip(), "thinking": thinking.replace("<think>", "", 1).strip(),
                "thinking_truncated": False}
    if thinking_enabled:
        # A learned direct-answer response can omit the thinking block. Recover
        # only a complete JSON object ending at EOS, never an arbitrary short
        # fragment. Task-specific validation still judges its exact schema.
        if ended_with_eos and "<think>" not in text:
            try:
                def unique_keys(pairs):
                    result = {}
                    for key, value in pairs:
                        if key in result:
                            raise ValueError("Duplicate JSON key")
                        result[key] = value
                    return result
                obj = json.loads(text, object_pairs_hook=unique_keys)
                if isinstance(obj, dict) and set(obj) in ({"answer"}, {"associations"}):
                    return {"text": text.strip(), "thinking": "", "thinking_truncated": False,
                            "format_deviation": "direct_json_without_thinking_block"}
            except (ValueError, TypeError):
                pass
        return {"text": "", "thinking": text.replace("<think>", "", 1).strip(), "thinking_truncated": True}
    return {"text": text.strip()}


def annealed_sampling_processor(spec, top_p, top_k):
    """Logits processor: scheduled temperature, then top-k, then nucleus filtering.

    Step 0 is the first generated token. ``temperatures`` records each applied
    value so the realized schedule is auditable, like the steering trace.
    """
    import torch
    from transformers import LogitsProcessor
    from .schedules import annealed_temperature, validate_temperature_schedule
    spec = validate_temperature_schedule(spec)

    class AnnealedSampling(LogitsProcessor):
        def __init__(self):
            self.temperatures = []

        def __call__(self, input_ids, scores):
            value = annealed_temperature(len(self.temperatures), spec)
            self.temperatures.append(value)
            scores = scores / value
            if top_k:
                kth = torch.topk(scores, min(top_k, scores.shape[-1]), dim=-1).values[..., -1, None]
                scores = scores.masked_fill(scores < kth, float("-inf"))
            if top_p < 1:
                ordered, index = torch.sort(scores, descending=True, dim=-1)
                cumulative = ordered.softmax(-1).cumsum(-1)
                # Drop tokens once the mass BEFORE them already exceeds top_p;
                # the most likely token is always kept.
                drop = (cumulative - ordered.softmax(-1)) > top_p
                scores = scores.masked_fill(drop.scatter(-1, index, drop), float("-inf"))
            return scores

    return AnnealedSampling()


def loop_share(ids, guard):
    """Share of repeated n-grams in the last ``window_tokens`` generated tokens.

    V1.3.3 loop guard (option A, David 2026-10-31): a reasoning loop repeats the
    same passage, so nearly every n-gram in the tail has appeared before in it.
    Returns None until the window is full. Pure, so it can be calibrated offline.
    """
    window, n = guard["window_tokens"], guard["ngram"]
    if len(ids) < window:
        return None
    tail = list(ids[-window:])
    seen, repeated = set(), 0
    for i in range(len(tail) - n + 1):
        gram = tuple(tail[i:i + n])
        repeated += gram in seen
        seen.add(gram)
    return repeated / (len(tail) - n + 1)


def loop_detected(ids, guard):
    share = loop_share(ids, guard)
    return share is not None and share >= guard["repeat_share"]


def loop_stopper(guard, prompt_length):
    """A Hugging Face stopping criterion that ends generation once loop_detected fires."""
    import torch
    from transformers import StoppingCriteria

    class LoopStop(StoppingCriteria):
        def __init__(self):
            self.fired_at = None

        def __call__(self, input_ids, scores, **kwargs):
            new = input_ids[0, prompt_length:]
            if self.fired_at is None and len(new) % guard["check_every"] == 0 and loop_detected(new.tolist(), guard):
                self.fired_at = len(new)
            # One flag per batch row, as StoppingCriteriaList combines them.
            return torch.full((input_ids.shape[0],), self.fired_at is not None, dtype=torch.bool, device=input_ids.device)
    return LoopStop()


def generate(model, tokenizer, text, *, system=None, max_input_tokens=1024,
             max_new_tokens=64, temperature=0.0, top_p=1.0, top_k=None, seed=0,
             temperature_schedule=None, loop_guard=None):
    import torch
    from .steering import assert_no_dream_hooks
    # Hook absence is asserted by callers for clean evaluation; exploration owns its hook.
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    model.eval()
    encoded = tokenizer(render_chat(tokenizer, text, system), return_tensors="pt", add_special_tokens=False)
    if encoded["input_ids"].shape[1] > max_input_tokens:
        raise ValueError("Prompt exceeds token budget; silent truncation is disabled")
    if encoded["input_ids"].shape[1] + max_new_tokens > model.config.max_position_embeddings:
        raise ValueError("Generation would exceed the model context window")
    device = model.get_input_embeddings().weight.device
    # V1.4.1: pass only the causal-LM inputs. A generic fast tokenizer (Mistral fast_json) also returns
    # token_type_ids, which generate() rejects; dropping it does not change the tokens.
    encoded = {k: v.to(device) for k, v in encoded.items() if k in ("input_ids", "attention_mask")}
    kwargs = dict(max_new_tokens=max_new_tokens, do_sample=temperature > 0,
                  pad_token_id=tokenizer.pad_token_id, eos_token_id=tokenizer.eos_token_id, use_cache=True)
    if temperature_schedule is not None:
        # One processor applies the per-token temperature BEFORE top-k/top-p, in
        # the usual order. Built-in warpers are neutralized so library ordering
        # of custom versus default processors cannot change the result.
        kwargs.update(do_sample=True, temperature=1.0, top_p=1.0, top_k=0,
                      logits_processor=[annealed_sampling_processor(temperature_schedule, top_p, top_k)])
    elif temperature > 0:
        kwargs.update(temperature=temperature, top_p=top_p)
        if top_k is not None:
            kwargs["top_k"] = top_k
    stopper = None
    if loop_guard is not None:
        stopper = loop_stopper(loop_guard, encoded["input_ids"].shape[1])
        kwargs["stopping_criteria"] = [stopper]
    with torch.no_grad():
        output = model.generate(**encoded, **kwargs)
    new = output[0, encoded["input_ids"].shape[1]:]
    thinking_enabled = getattr(tokenizer, "dream_chat_kwargs", {}).get("enable_thinking", False)
    raw_text = tokenizer.decode(new, skip_special_tokens=True)
    ended_with_eos = bool(new.numel() and int(new[-1]) == tokenizer.eos_token_id)
    looped = stopper is not None and stopper.fired_at is not None
    finish = "eos" if ended_with_eos else "loop" if looped else "length" if len(new) >= max_new_tokens else "other"
    return {**split_thinking(raw_text, thinking_enabled, ended_with_eos=ended_with_eos),
            "raw_text": raw_text, "ended_with_eos": ended_with_eos, "finish_reason": finish,
            # A looped answer is kept whole; the excerpt shows the repeated tail.
            **({"loop": {"stopped_at_token": stopper.fired_at, "guard": dict(loop_guard),
                         "repeated_tail": tokenizer.decode(new[-loop_guard["window_tokens"]:], skip_special_tokens=True)}}
               if looped else {}),
            "input_tokens": int(encoded["input_ids"].shape[1]), "output_tokens": int(new.shape[0]),
            **({"temperature_trace": kwargs["logits_processor"][0].temperatures} if temperature_schedule is not None else {})}
