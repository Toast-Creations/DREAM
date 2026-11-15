"""Verify the actual summary clusters seeds within independent worlds."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("release_analysis",ROOT/"scripts/summarize_runs.py")
analysis=importlib.util.module_from_spec(spec);spec.loader.exec_module(analysis)


def trial(world,seed,condition,lam,value):
    return {"status":"completed","world_id":world,"seed":seed,"condition":condition,
            "lambda":lam,"eta":1.0,"metrics":{"accuracy":{"composition":value}}}


class AnalysisTests(unittest.TestCase):
    def test_seeds_are_averaged_inside_worlds(self):
        rows=[trial("a",1,"plasticity_only",0,.2),trial("a",1,"coupled",.1,.4),
              trial("a",2,"plasticity_only",0,.6),trial("a",2,"coupled",.1,.2),
              trial("b",1,"plasticity_only",0,.2),trial("b",1,"coupled",.1,.8)]
        result=analysis.paired_world_summary(rows)[0]
        self.assertEqual(result["worlds"],2)
        self.assertAlmostEqual(result["mean_paired_composition_gain"],.25)

    def test_one_world_has_no_claimed_interval(self):
        rows=[trial("a",1,"plasticity_only",0,.2),trial("a",1,"coupled",.1,.4)]
        self.assertIsNone(analysis.paired_world_summary(rows)[0]["exploratory_world_bootstrap_95_interval"])

    def test_unpaired_rows_do_not_become_evidence(self):
        self.assertEqual(analysis.paired_world_summary([trial("a",1,"coupled",.1,.8)]),[])


if __name__=="__main__":unittest.main()
