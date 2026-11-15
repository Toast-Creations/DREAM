"""V1.6.0 explicit-context decision study (proposal draft 1.1, 2026-11-04).

world.py    solver 1: STRIPS grounding + Dijkstra (used to construct items)
keycheck.py solver 2: direct per-family simulation + Bellman-Ford relaxation (independent check)
generate.py seeded episode generator (three families, fact-flip pairs, controls, corrections)
render.py   the exact text every condition sees
"""
