"""Rebuild deterministic release fixtures without downloading models."""
import json
from pathlib import Path
from _bootstrap import ROOT
from dream2.worlds import generate_worlds, validate_worlds


def write(path, value):
    path=ROOT/path; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8")


def main():
    worlds=[]; smoke=[]
    for offset,split in enumerate(("development","validation","test")):
        group=generate_worlds(12,1101+100000*offset,split)
        worlds+=group; smoke+=group[:1]
    validate_worlds(worlds)
    for name,items in (("microworlds.jsonl",worlds),("microworlds-smoke.jsonl",smoke)):
        path=ROOT/"data"/name; path.parent.mkdir(exist_ok=True)
        path.write_text("\n".join(json.dumps(w,separators=(",",":")) for w in items)+"\n",encoding="utf-8")
    tasks=[]
    task_definitions=[
        ("analogy","Explain a structural analogy between queue congestion and another system. State two limits of the analogy. Avoid proposing real infrastructure changes."),
        ("symbolic_design","Propose three abstract connected patterns on a square grid. Explain why each has one connected component. Treat this as a graph exercise, not a construction drawing."),
        ("algorithm","Compare three ways of representing a toy scheduling problem with six jobs and two shared resources. State how each representation could be checked."),
        ("negative_control","Compute 17 plus 26 and state the result. A distant analogy is unnecessary; preserve exact arithmetic."),
        ("reasoning","Give two different proofs that the sum of two even integers is even. State the assumptions."),
        ("creative_synthesis","Invent three fictional delivery systems on a square game board using movement rules and state how to test whether each can deadlock.")]
    for split in ("development","validation","test"):
        for index,(category,prompt) in enumerate(task_definitions):
            # Distinct variants, rather than relabeling the same prompt across splits.
            variants={"development":"Use a small example of your choice.",
                      "validation":"Use a different example involving exactly four distinguishable objects.",
                      "test":"Use a counterexample and an explicit boundary case."}
            tasks.append({"id":f"{split}-task-{index:02d}","split":split,"category":category,
                          "prompt":prompt+" "+variants[split],"verification":"human or symbolic checker required"})
    for name,items in (("tasks.jsonl",tasks),("tasks-smoke.jsonl",[t for t in tasks if t["category"]=="negative_control"])):
        (ROOT/"data"/name).write_text("\n".join(json.dumps(t) for t in items)+"\n",encoding="utf-8")
    write("data/steering_prompts.json",[
        {"convergent":"Study a toy symbolic system using its direct literal interpretation. Preserve all facts and constraints.",
         "divergent":"Study a toy symbolic system using alternative structural interpretations. Preserve all facts and constraints."},
        {"convergent":"Represent a graph puzzle using one standard formulation and identify its constraints.",
         "divergent":"Represent a graph puzzle using several equivalent formulations and identify invariant constraints."},
        {"convergent":"Describe a queue using a conventional local description and check the stated assumptions.",
         "divergent":"Describe a queue using distant structural analogies and check the stated assumptions."},
        {"convergent":"Use one familiar abstraction to explain a transformation and show where it fails.",
         "divergent":"Compare multiple alternative abstractions for a transformation and show where each fails."}])
    base={"version":"1.1.0","phase":"development","seeds":[11],"model":{"path":None,"manifest":None,"device":"cuda","dtype":"bfloat16"},
        "output_dir":"../runs","steering":{"layer_index":-8,"lambda_values":[0.0,0.05],"vector_path":"../artifacts/steering-V1.1.json","schedule":True},
        "limits":{"max_trials":8,"max_seconds":1800,"max_input_tokens":1024,"max_new_tokens":32,"max_worlds":1},
        "gate":{"enabled":False,"min_composition_gain":None,"max_anchor_regression":None,"max_error_rate":None,"min_items_per_category":None}}
    for experiment in ("dream","dream2"):
        cfg=json.loads(json.dumps(base)); cfg["experiment"]=experiment
        cfg["data_path"]="../data/"+("microworlds-smoke.jsonl" if experiment=="dream2" else "tasks-smoke.jsonl")
        if experiment=="dream2":
            cfg.update(adapter={"rank":8,"alpha":16,"target_modules":["q_proj","v_proj"],"optimizer":"adamw",
                "base_learning_rate":0.0001,"max_grad_norm":1.0,"steps_per_example":1},
                plasticity={"eta_values":[0.0,1.0],"preexposure_control":True,"high_eta":2.0},verify_base_each_trial=True)
        else:
            cfg["generation"]={"temperature":0.7,"high_temperature":1.3,"integration_temperature":0.3,"top_p":0.9}
        write(f"configs/{experiment}-smoke.json",cfg)
        pilot=json.loads(json.dumps(cfg)); pilot["seeds"]=[11,22,33]
        pilot["data_path"]=pilot["data_path"].replace("-smoke","")
        pilot["limits"].update(max_trials=600,max_seconds=7200,max_worlds=12,max_new_tokens=64,max_input_tokens=1536)
        pilot["steering"]["lambda_values"]=[0.0,0.05,0.1]
        if experiment=="dream2": pilot["plasticity"]["eta_values"]=[0.0,0.5,1.0]
        write(f"configs/{experiment}-pilot.json",pilot)
    print("Built verified fixtures and four V1.1 configs")


if __name__=="__main__": main()
