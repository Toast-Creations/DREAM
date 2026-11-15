"""Temporal pilot (V1.7.0): state tracking, corrections, delayed reports and one-step prediction.

Static inference only. No adapters, no training, no steering. See documents in the run hub's design/ folder.
Modules: worlds (domains + planner bridges), records (typed evidence records), resolve (resolver 1),
enumcheck (resolver 2 + independent action checker), generate (patterns, padding, variants, gold),
render (prompts), score (strict parsing and scoring).
"""
VERSION = "1.9.1"
