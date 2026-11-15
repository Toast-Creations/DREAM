"""Create checksummed V1.3.1 source distributions and a combined project archive."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import zipfile
from _bootstrap import ROOT
from dream_core.ledger import atomic_json,file_hash

EXCLUDED={"__pycache__",".venv",".git","runs","models","artifacts","dist","temporary"}


def files():
    return [p for p in sorted(ROOT.rglob("*")) if p.is_file() and
            not EXCLUDED.intersection(p.relative_to(ROOT).parts) and p.suffix not in (".pyc",".tmp")
            and p.name!="MANIFEST.json"]


def main():
    if not (ROOT/"handbook/DREAM-Project-Handbook-V1.3.1.pdf").is_file():
        raise FileNotFoundError("Build and visually inspect the handbook before packaging")
    originals={"DREAM-research-package-v0.1.zip":"03e10996e01e3ade7910a95fe10e1593f0796c4f097e00e99471e7832dc412b0",
               "DREAM2-research-package-v0.1.zip":"ad31ad704233847c8e53f51f6f13efd0fc76602a63afbdd6b6e93bfa8605aa67"}
    verified=[]
    for name,expected in originals.items():
        path=ROOT.parent.parent/name
        if path.is_file() and file_hash(path)!=expected: raise ValueError("Original archive changed: "+name)
        verified.append({"name":name,"sha256":expected,"present_and_verified":path.is_file()})
    (ROOT/"provenance").mkdir(exist_ok=True)
    atomic_json(ROOT/"provenance/original-archives.json",{"originals":verified,
        "note":"Preserved V0.1 archives. Hashes identify content, not an independently established invention date."})
    selection=files()
    manifest={"project":"DREAM and DREAM 2","version":"1.3.1","project_lead":"David Cook",
        "built_at_utc":datetime.now(timezone.utc).isoformat(),"status":"research prototype; see measured current tests and exploratory study records",
        "files":[{"path":p.relative_to(ROOT).as_posix(),"bytes":p.stat().st_size,"sha256":file_hash(p)} for p in selection]}
    atomic_json(ROOT/"MANIFEST.json",manifest)
    dist=ROOT/"dist";dist.mkdir(exist_ok=True)
    archives=[]
    for label in ("DREAM","DREAM2"):
        path=dist/f"{label}-research-package-V1.3.1.zip"
        prefix=f"{label}-research-package-V1.3.1/"
        focus=(f"# {label} Package V1.3.1\n\nThis distribution focuses on {label}. Both experiments, shared safeguards, tests, the bibliography, and the full document set are included so the source remains consistent.\n\n"
               f"Start with [the research paper](documents/{'02-DREAM-Research-Paper.md' if label=='DREAM' else '03-DREAM2-Research-Paper.md'}) and [the smoke configuration](configs/{'dream' if label=='DREAM' else 'dream2'}-smoke.json).\n\nRead [method credits](METHOD_CREDITS.md), [the bibliography](references.bib), and [all sources](documents/12-References-and-Method-Credits.md). The combined project is the authoritative editing tree. No model weights are included.\n")
        with zipfile.ZipFile(path,"w",zipfile.ZIP_DEFLATED) as archive:
            for p in selection:archive.write(p,prefix+p.relative_to(ROOT).as_posix())
            archive.writestr(prefix+"PACKAGE_FOCUS.md",focus)
            focused_manifest={**manifest,"focus":label,"files":manifest["files"]+[
                {"path":"PACKAGE_FOCUS.md","bytes":len(focus.encode()),"sha256":hashlib.sha256(focus.encode()).hexdigest()}]}
            archive.writestr(prefix+"MANIFEST.json",json.dumps(focused_manifest,indent=2)+"\n")
        archives.append(path)
    combined=dist/"DREAM-Project-V1.3.1-Complete.zip"
    with zipfile.ZipFile(combined,"w",zipfile.ZIP_DEFLATED) as archive:
        for p in selection:archive.write(p,"DREAM-project-V1.3.1/"+p.relative_to(ROOT).as_posix())
        for p in archives:archive.write(p,"DREAM-project-V1.3.1/standalone-packages/"+p.name)
        combined_manifest={**manifest,"files":manifest["files"]+[
            {"path":"standalone-packages/"+p.name,"bytes":p.stat().st_size,"sha256":file_hash(p)} for p in archives]}
        archive.writestr("DREAM-project-V1.3.1/MANIFEST.json",json.dumps(combined_manifest,indent=2)+"\n")
    for path in archives+[combined]:
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None: raise RuntimeError("Archive CRC check failed")
    summary={"files":len(selection)+1,"documents":len(list((ROOT/"documents").glob("[0-9][0-9]-*.md"))),
             "archives":[{"name":p.name,"bytes":p.stat().st_size,"sha256":file_hash(p)} for p in archives+[combined]]}
    atomic_json(dist/"release-summary.json",summary)
    print(json.dumps(summary,indent=2))


if __name__=="__main__":main()
