"""No downloads: real PyTorch/Qwen2/PEFT tests when optional dependencies exist."""
import importlib.util
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
AVAILABLE=all(importlib.util.find_spec(n) is not None for n in ("torch","transformers","peft","safetensors"))


@unittest.skipUnless(AVAILABLE,"PyTorch, Transformers, PEFT, safetensors required; not installed in release authoring runtime")
class ModelIntegrationTests(unittest.TestCase):
    def setUp(self):
        import torch
        from transformers import Qwen2Config,Qwen2ForCausalLM
        from dream2.plasticity import attach_adapter
        self.torch=torch
        torch.manual_seed(9)
        base=Qwen2ForCausalLM(Qwen2Config(vocab_size=64,hidden_size=32,intermediate_size=64,
            num_hidden_layers=2,num_attention_heads=4,num_key_value_heads=2,max_position_embeddings=1024,
            attention_dropout=0.0,bos_token_id=1,eos_token_id=2,pad_token_id=0))
        for p in base.parameters(): p.requires_grad_(False)
        self.model=attach_adapter(base,{"rank":2,"alpha":4,"target_modules":["q_proj","v_proj"]})
        self.model.eval()
        self.ids=torch.tensor([[3,4,5,6,7,8]])
        self.labels=torch.tensor([[-100,-100,-100,6,7,8]])
        self.vector=torch.randn(32); self.vector/=self.vector.norm()

    def loss_and_gradient(self,strength,mask):
        from dream_core.steering import MaskedSteerer
        from dream2.plasticity import adapter_parameters
        self.model.zero_grad(set_to_none=True)
        with MaskedSteerer(self.model,0,self.vector,strength,mask=mask):
            loss=self.model(input_ids=self.ids,labels=self.labels,use_cache=False).loss
            loss.backward()
        grad=self.torch.cat([p.grad.flatten() for p in adapter_parameters(self.model).values() if p.grad is not None]).clone()
        return loss.detach(),grad

    def test_final_only_bug_reproduced_and_corrected_mask_changes_gradient(self):
        from dream_core.contracts import predictor_mask
        zero,g0=self.loss_and_gradient(0,[[False]*6])
        last,glast=self.loss_and_gradient(.2,[[False]*5+[True]])
        fixed,gfixed=self.loss_and_gradient(.2,[predictor_mask(self.labels[0].tolist())])
        self.torch.testing.assert_close(zero,last,rtol=0,atol=1e-6)
        self.torch.testing.assert_close(g0,glast,rtol=0,atol=1e-6)
        self.assertGreater(float((g0-gfixed).norm()),1e-7)

    def test_exception_rolls_back_and_base_unchanged(self):
        from dream2.plasticity import adapter_hash,adapter_parameters,base_hash,reversible_trial,snapshot
        from dream_core.steering import MaskedSteerer,assert_no_dream_hooks
        before=snapshot(self.model); ah=adapter_hash(self.model); bh=base_hash(self.model)
        with self.assertRaises(RuntimeError):
            with reversible_trial(self.model,before):
                with MaskedSteerer(self.model,0,self.vector,.1,mask=[[True]*5+[False]]):
                    with self.torch.no_grad():
                        next(iter(adapter_parameters(self.model).values())).add_(1)
                    raise RuntimeError("injected")
        self.assertEqual(adapter_hash(self.model),ah)
        self.assertEqual(base_hash(self.model),bh)
        assert_no_dream_hooks(self.model)

    def test_extra_trainable_base_parameter_is_rejected(self):
        from dream2.plasticity import adapter_parameters
        for name,p in self.model.named_parameters():
            if ".lora_" not in name:
                p.requires_grad_(True)
                break
        with self.assertRaises(RuntimeError): adapter_parameters(self.model)

    def test_zero_eta_invariance_and_one_step_update(self):
        from dream_core.contracts import predictor_mask
        from dream2.plasticity import adapter_hash,adapter_parameters
        before=adapter_hash(self.model)
        self.loss_and_gradient(.2,[predictor_mask(self.labels[0].tolist())])
        self.assertEqual(adapter_hash(self.model),before)
        optimizer=self.torch.optim.SGD(list(adapter_parameters(self.model).values()),lr=.1)
        optimizer.step()
        self.assertNotEqual(adapter_hash(self.model),before)

    def test_actual_training_function_zero_eta_and_update(self):
        from dream2.plasticity import adapter_hash
        from dream2.training import learn
        from dream2.worlds import generate_worlds
        # A local deterministic tokenizer fixture; no network or vocabulary download.
        torch=self.torch
        class Tokenizer:
            eos_token_id=2
            chat_template="local-test-template"
            def apply_chat_template(self,messages,**kwargs):
                return " ".join(m["content"] for m in messages)+" Answer:"
            def encode(self,text,**kwargs):
                return [3+(b%60) for b in text.encode("utf-8")]
        world=generate_worlds(1)[0]; world["train"]=world["train"][:1]
        cfg={"adapter":{"optimizer":"adamw","base_learning_rate":.001,"max_grad_norm":1.0,
            "steps_per_example":1},"limits":{"max_input_tokens":1024},"steering":{"layer_index":0}}
        before=adapter_hash(self.model)
        diagnostics=learn(self.model,Tokenizer(),world,cfg,self.vector,.1,0)
        self.assertEqual(adapter_hash(self.model),before)
        self.assertFalse(diagnostics[0]["updated"])
        diagnostics=learn(self.model,Tokenizer(),world,cfg,self.vector,.1,1)
        self.assertNotEqual(adapter_hash(self.model),before)
        self.assertGreater(diagnostics[0]["supervised_predictions"],0)

    def test_signed_trip_steering_trace_and_comedown(self):
        from dream_core.steering import MaskedSteerer,assert_no_dream_hooks,blocks,hidden_tensor
        torch=self.torch
        def block_output(lam):
            # A hook registered after the steerer's sees its replaced output.
            seen=[]
            context=(MaskedSteerer(self.model,0,self.vector,lam,generation=True,schedule_spec={"shape":"constant"})
                     if lam else None)
            if context: context.__enter__()
            handle=blocks(self.model)[0].register_forward_hook(lambda m,i,o:seen.append(hidden_tensor(o).clone()))
            try: self.model(input_ids=self.ids,use_cache=False)
            finally:
                handle.remove()
                if context: context.__exit__(None,None,None)
            return seen[0]
        with torch.no_grad():
            clean=block_output(0)
            deltas={lam:(block_output(lam)-clean)[0,-1] for lam in (.2,-.2)}
            self.assertGreater(float(deltas[.2].norm()),0)
            torch.testing.assert_close(deltas[.2],-deltas[-.2],rtol=1e-4,atol=1e-5)
            self.assertGreater(float(torch.dot(deltas[.2],self.vector)),0)
            spec={"shape":"smooth","onset_tokens":2,"plateau_tokens":1,"comedown_tokens":2}
            with MaskedSteerer(self.model,0,self.vector,-.1,generation=True,schedule_spec=spec) as steerer:
                for _ in range(4): self.model(input_ids=self.ids,use_cache=False)
                self.assertFalse(steerer.comedown_complete)
                for _ in range(3): self.model(input_ids=self.ids,use_cache=False)
            self.assertTrue(steerer.comedown_complete)
            self.assertEqual(len(steerer.trace),7)
            self.assertEqual(steerer.trace[0],0.0); self.assertAlmostEqual(min(steerer.trace),-.1)
            self.assertEqual(steerer.trace[5:],[0.0,0.0])
            assert_no_dream_hooks(self.model)
        with self.assertRaises(ValueError):
            MaskedSteerer(self.model,0,self.vector,-.1,mask=[[True]*6])
        with self.assertRaises(ValueError):
            MaskedSteerer(self.model,0,self.vector,.1,generation=True,schedule=True,schedule_spec={"shape":"constant"})

    def test_named_poles_and_vector_kind_binding(self):
        import json
        from pathlib import Path
        from dream_core.steering import build_vector,load_vector
        from test_core import test_directory
        class Tokenizer:
            def __call__(self,text,return_tensors=None,add_special_tokens=False):
                return {"input_ids":self_torch.tensor([[3+(b%60) for b in text.encode()][:20]])}
        self_torch=self.torch
        tok=Tokenizer()
        import dream_core.modeling as modeling
        original=modeling.render_chat; modeling.render_chat=lambda t,text,system=None:text
        try:
            pairs=[{"decategorized":"a pattern anywhere","categorical":"one more organ"},
                   {"decategorized":"a mechanism elsewhere","categorical":"typical member"}]
            v=build_vector(self.model,tok,pairs,0,64,poles=("decategorized","categorical"))
            swapped=build_vector(self.model,tok,pairs,0,64,poles=("categorical","decategorized"))
            self.torch.testing.assert_close(v,-swapped,rtol=1e-4,atol=1e-5)
            with self.assertRaises(KeyError):
                build_vector(self.model,tok,pairs,0,64)
        finally:
            modeling.render_chat=original
        with test_directory() as directory:
            path=Path(directory)/"v.json"
            path.write_text(json.dumps({"model_manifest_sha256":"m","layer":0,"vector":v.tolist(),"kind":"random"}))
            load_vector(path,self.model,"m",0,kind="random")
            with self.assertRaisesRegex(ValueError,"kind"):
                load_vector(path,self.model,"m",0,kind="decategorization")

    def test_annealed_sampling_processor_order_and_trace(self):
        from dream_core.modeling import annealed_sampling_processor
        torch=self.torch
        proc=annealed_sampling_processor({"start":2.0,"end":0.5,"anneal_tokens":4},top_p=0.9,top_k=3)
        scores=torch.tensor([[4.0,3.0,2.0,1.0,0.0]])
        first=proc(None,scores.clone())
        self.assertEqual(proc.temperatures,[2.0])
        self.assertTrue(torch.isinf(first[0,3:]).all())
        kept=torch.isfinite(first[0]).sum().item()
        self.assertGreaterEqual(kept,1); self.assertLessEqual(kept,3)
        for _ in range(5): proc(None,scores.clone())
        self.assertEqual(proc.temperatures[-1],0.5)

    def test_generate_with_temperature_schedule_and_trip_on_real_generate(self):
        from dream_core.modeling import generate
        from dream_core.steering import MaskedSteerer
        torch=self.torch
        class Tokenizer:
            eos_token_id=2; pad_token_id=0; chat_template="local-test-template"
            def apply_chat_template(self,messages,**kwargs): return " ".join(m["content"] for m in messages)
            def __call__(self,text,return_tensors=None,add_special_tokens=False):
                ids=torch.tensor([[3+(b%60) for b in text.encode()][:16]])
                return {"input_ids":ids,"attention_mask":torch.ones_like(ids)}
            def decode(self,ids,skip_special_tokens=True): return " ".join(str(int(x)) for x in ids)
        tok=Tokenizer()
        out=generate(self.model,tok,"pump",max_new_tokens=6,temperature=0.6,top_p=0.95,top_k=20,seed=3,
                     temperature_schedule={"start":1.3,"end":0.6,"anneal_tokens":4})
        self.assertEqual(len(out["temperature_trace"]),out["output_tokens"])
        self.assertAlmostEqual(out["temperature_trace"][0],1.3)
        spec={"shape":"smooth","onset_tokens":2,"plateau_tokens":2,"comedown_tokens":2}
        with MaskedSteerer(self.model,0,self.vector,.1,generation=True,schedule_spec=spec) as steerer:
            out=generate(self.model,tok,"pump",max_new_tokens=8,temperature=0.6,top_p=0.95,top_k=20,seed=3)
        self.assertEqual(len(steerer.trace),out["output_tokens"])
        self.assertEqual(steerer.comedown_complete,out["output_tokens"]>6)

    def concept_tokenizer(self):
        torch=self.torch
        class Tokenizer:
            eos_token_id=2; pad_token_id=0; chat_template="local-test-template"
            def __init__(self): self.rendered=[]
            def apply_chat_template(self,messages,**kwargs):
                self.rendered.append(kwargs.get("enable_thinking"))
                return " ".join(m["content"] for m in messages)+" Answer:"
            def encode(self,text,**kwargs): return [3+(b%60) for b in text.encode("utf-8")]
            def __call__(self,text,return_tensors=None,add_special_tokens=False):
                ids=torch.tensor([[3+(b%60) for b in text.encode()][-64:]])
                return {"input_ids":ids,"attention_mask":torch.ones_like(ids)}
            def decode(self,ids,skip_special_tokens=True): return " ".join(str(int(x)) for x in ids)
        return Tokenizer()

    def test_concept_learning_text_target_trains_with_thinking_off(self):
        # V1.3.3: closed-book text targets, rendered with thinking off; eta=0 leaves the adapter.
        from dream2.concept_worlds import load_concept_worlds
        from dream2.plasticity import adapter_hash
        from dream2.training import learn, prepare_example
        world=load_concept_worlds(ROOT/"data/concept-worlds-smoke.jsonl","development")[0]
        world["train"]=[next(i for i in world["train"] if i["book"]=="closed")]
        tok=self.concept_tokenizer(); tok.dream_chat_kwargs={"enable_thinking":True}
        encoded,mask=prepare_example(tok,world,world["train"][0],4096)
        self.assertEqual(tok.rendered[-1],False)
        target=tok.encode(world["train"][0]["target_text"])+[2]
        self.assertEqual(encoded["labels"][0,-len(target):].tolist(),target)
        self.assertEqual(sum(mask[0]),len(target))
        cfg={"adapter":{"optimizer":"adamw","base_learning_rate":.001,"max_grad_norm":1.0,
            "steps_per_example":2},"limits":{"max_input_tokens":4096},"steering":{"layer_index":0}}
        before=adapter_hash(self.model)
        self.assertEqual(len(learn(self.model,tok,world,cfg,self.vector,.1,0)),2)
        self.assertEqual(adapter_hash(self.model),before)
        learn(self.model,tok,world,cfg,self.vector,.1,1)
        self.assertNotEqual(adapter_hash(self.model),before)

    def test_concept_evaluation_pairs_seeds_and_restores_reasoning_switch(self):
        from dream2.concept_evaluation import concept_metrics, evaluate_concepts
        from dream2.concept_worlds import load_concept_worlds
        from dream_core.config import load_config
        world=load_concept_worlds(ROOT/"data/concept-worlds-smoke.jsonl","development")[0]
        cfg=load_config(ROOT/"configs/dream2-concepts-smoke.json"); cfg["limits"]["max_new_tokens"]=4
        tok=self.concept_tokenizer(); tok.dream_chat_kwargs={"enable_thinking":True}
        rows=evaluate_concepts(self.model,tok,world,cfg,11)
        again=evaluate_concepts(self.model,tok,world,cfg,11)
        self.assertEqual(len(rows),len(world["eval"])*2)
        self.assertEqual([r["text"] for r in rows],[r["text"] for r in again])
        self.assertEqual(tok.rendered,[False,True]*len(world["eval"])*2)
        self.assertEqual(tok.dream_chat_kwargs,{"enable_thinking":True})
        self.assertEqual(set(concept_metrics(rows,rows)),{"direct","thinking"})

    def test_real_generate_stops_on_loop(self):
        # A tiny random model decoding greedily repeats itself; the guard must stop it early.
        from dream_core.modeling import generate
        tok=self.concept_tokenizer()
        guard={"window_tokens":64,"ngram":4,"repeat_share":0.8,"check_every":8}
        out=generate(self.model,tok,"pump pump",max_new_tokens=600,temperature=0,seed=1,loop_guard=guard)
        plain=generate(self.model,tok,"pump pump",max_new_tokens=600,temperature=0,seed=1)
        self.assertEqual(out["finish_reason"],"loop")
        self.assertLess(out["output_tokens"],plain["output_tokens"])
        self.assertEqual(out["loop"]["stopped_at_token"],out["output_tokens"])
        self.assertNotIn("loop",plain)

    def test_concept_conditions_include_coupled_decat(self):
        from dream2.experiment import conditions
        from dream_core.config import load_config
        from dream_core.planning import trial_count
        cfg=load_config(ROOT/"configs/dream2-concepts-pilot.json")
        cells=conditions(cfg)
        self.assertEqual(len(cells)*6,trial_count(cfg,6))
        decat=[c for c in cells if c.get("vector")=="decat"]
        self.assertEqual([(c["condition"],c["lambda"],c["eta"]) for c in decat],[("coupled_decat",0.2,1.0)])

    def test_mask_shape_and_nonfinite_vector_rejected(self):
        from dream_core.steering import MaskedSteerer
        with self.assertRaises(ValueError):
            with MaskedSteerer(self.model,0,self.vector,.1,mask=[[True]]):
                self.model(input_ids=self.ids,use_cache=False)
        vector=self.vector.clone(); vector[0]=float("nan")
        with self.assertRaises(ValueError):
            MaskedSteerer(self.model,0,vector,.1,mask=[[True]*6])


if __name__=="__main__": unittest.main()
