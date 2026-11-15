"""Export DREAM 1 outputs for independent ratings, with a separate private key."""
import argparse
import csv
import json
from pathlib import Path
import random
import uuid
from _bootstrap import ROOT
from dream_core.export import spreadsheet_safe


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument("run_directory")
    args=parser.parse_args(); root=Path(args.run_directory).resolve()
    rows=[]; key=[]
    for p in sorted(root.glob("trial-*.json")):
        trial=json.loads(p.read_text(encoding="utf-8"))
        if "integrated" not in trial: continue
        sample=uuid.uuid4().hex
        rows.append({"sample_id":sample,"task_id":trial["task_id"],"output":trial["integrated"]["text"],
                     "novelty_1to5":"","usefulness_1to5":"","correctness_1to5":"","coherence_1to5":"","evidence_notes":""})
        key.append({"sample_id":sample,"trial_file":p.name,"condition":trial["condition"],"lambda":trial["lambda"],"seed":trial["seed"]})
    if not rows: raise ValueError("No DREAM 1 trials found")
    random.Random(1101).shuffle(rows)
    for filename,items in (("reviewer.csv",rows),("private-condition-key.csv",key)):
        with (root/filename).open("x",encoding="utf-8",newline="") as stream:
            writer=csv.DictWriter(stream,fieldnames=list(items[0])); writer.writeheader()
            writer.writerows({k:spreadsheet_safe(v) for k,v in item.items()} for item in items)
    print("Reviewer table and separate private condition key saved. Give reviewers the original tasks and rubric; keep the key private.")


if __name__=="__main__": main()
