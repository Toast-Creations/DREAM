# Contributing

Prioritize independent criticism, reproducible counterexamples, and replication. Record actual contributions, cite the closest prior work, and preserve David Cook's project attribution without claiming that every underlying method originated here.

Changes affecting the intervention, supervision mask, prompt, scorer, oracle, layer, precision, optimizer, benchmark, selection gate, or analysis require corresponding tests and a protocol change record. Do not change a held-out benchmark after seeing its outcomes without identifying the analysis as exploratory.

Run scripts/run_tests.py and scripts/run_tests.py --require-ml in a functioning ML environment. The latter must fail when model coverage is missing. Report skipped checks explicitly.

Do not add model-controlled external tools, private-data ingestion, remote code loading, automatic model publication, unverified self-training, or deployment. Such changes exceed this prototype's scope and require a separately specified research design.

Agree on authorship and data access before substantial collaboration. Preserve applicable copyright and third-party notices. Do not add a citation restriction to Apache-2.0 as though it were part of that standard license.
