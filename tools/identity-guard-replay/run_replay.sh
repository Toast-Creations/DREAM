#!/usr/bin/env bash
# IGUARD-v0.1 bounded CPU replay. Usage: ./run_replay.sh RESULTS_HUB
# Runs inside the dream-research container with the research venv. No GPU, no model, no network.
#
# Whole-run cap: CAP=1800 s from start to final status, INCLUDING reporting. The stage pipeline runs under
# `timeout`, which signals its whole process group (every stage child); each container call is additionally bounded
# by a container-side `timeout` set to the remaining seconds. Every stage process (host or in-container; distrobox
# shares the host PID namespace) carries a per-run IGUARD_RUN_TOKEN, and the driver sweeps all processes holding
# that token after the pipeline ends, so processes outside the pipeline's process group are terminated too.
# On timeout or interruption all children are terminated, TERMINAL.json / RUNTIME.json / READINESS.json / RUN-STATUS.md / REPORT.md record the terminal failure
# (earlier copies are kept as *.superseded-by-<TERMINAL>), and the exit code is nonzero.
# IGUARD_CAP_SECONDS may only TIGHTEN the cap (integer 1..1800, for tests); anything else is refused.
#
# Exit codes: 0 technically COMPLETE (READY or NOT READY is recorded in READINESS.json; an unfavourable outcome is
#             not a failure); 1 refused before starting; 2 a stage failed / inputs incomplete / report incomplete;
#             124 whole-run cap reached (children terminated); 130 interrupted (children terminated).
set -uo pipefail
U="$(cd "$(dirname "$0")" && pwd)"
PY=${DREAM_PY:-python}
CAP_MAX=1800
KILL_GRACE=5

# ------------------------------------------------------------------------------------------------ stage pipeline
if [ "${1:-}" = "--inner" ]; then
  HUB="$2"
  [ "${IGUARD_INNER_OK:-}" = 1 ] || { echo "internal mode: run ./run_replay.sh RESULTS_HUB"; exit 1; }
  cd "$U" || exit 2
  COMMIT="$IGUARD_COMMIT"; DEADLINE="$IGUARD_DEADLINE"; CAP="$IGUARD_CAP"; T0="$IGUARD_T0"
  export PYTHONDONTWRITEBYTECODE=1
  log() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$HUB/replay.log"; }
  remaining() { echo $((DEADLINE - $(date +%s))); }
  run() {
    local rem; rem=$(remaining)
    if [ "$rem" -le 0 ]; then echo "whole-run cap exhausted"; return 124; fi
    distrobox enter dream-research -- env IGUARD_RUN_TOKEN="$IGUARD_RUN_TOKEN" timeout -k "$KILL_GRACE" "$rem" \
      env IGUARD_RUN_TOKEN="$IGUARD_RUN_TOKEN" PYTHONDONTWRITEBYTECODE=1 CUDA_VISIBLE_DEVICES= "$PY" -B "$@"
  }
  FAILED=()
  step() {
    local name="$1"; shift; log "BEGIN $name"
    "$@" 2>&1 | tee -a "$HUB/replay.log"; local rc=${PIPESTATUS[0]}
    log "END $name rc=$rc"; [ "$rc" = 0 ] || FAILED+=("$name rc=$rc")
    if [ "$rc" != 0 ] && [ "$(remaining)" -le 0 ]; then log "whole-run cap reached during $name: stopping"; exit 124; fi
    return "$rc"
  }
  skip() { log "SKIP $1: $2"; FAILED+=("$1 skipped: $2"); }
  tests_stage() { run -m unittest discover -s tests -v > "$HUB/tests/TESTS.log" 2>&1; }
  sha() { [ -f "$1" ] && sha256sum "$1" | cut -d' ' -f1; }
  jstr() { local IFS=,; local out=() x; for x in "$@"; do out+=("\"${x//\"/}\""); done; echo "[${out[*]}]"; }

  PB=0; PLAN_OK=0; TESTS_OK=0
  step preserve-before run scripts/ig_preserve.py snapshot "$HUB/PRESERVE-BEFORE.json" && PB=1
  if [ $PB = 1 ]; then
    step plan run scripts/ig_plan.py --hub "$HUB" --commit "$COMMIT" && PLAN_OK=1
    run -c "import platform;print(platform.python_version())" > "$HUB/tests/python-version.txt" 2>&1
    step tests tests_stage && TESTS_OK=1
    echo "{\"ok\": $([ $TESTS_OK = 1 ] && echo true || echo false), \"log\": \"tests/TESTS.log\", \"commit\": \"$COMMIT\"}" > "$HUB/tests/TESTS.json"
    step controls run scripts/ig_controls.py --out "$HUB/controls"
  else
    for x in plan tests controls; do skip "$x" "preserve-before failed"; done
  fi
  DET=()
  for S in V1.24 V1.22; do
    eq=false; a=""; b=""
    if [ $PB = 1 ] && [ $PLAN_OK = 1 ] && [ $TESTS_OK = 1 ]; then
      if step "decide-$S" run scripts/ig_decide.py --study "$S" --out "$HUB/decisions"; then
        if step "decide-repeat-$S" run scripts/ig_decide.py --study "$S" --out "$HUB/decisions-repeat"; then
          a=$(sha "$HUB/decisions/DECISIONS-$S.jsonl"); b=$(sha "$HUB/decisions-repeat/DECISIONS-$S.jsonl")
          if [ -n "$a" ] && [ "$a" = "$b" ] && cmp -s "$HUB/decisions/DECISIONS-$S.jsonl" "$HUB/decisions-repeat/DECISIONS-$S.jsonl"; then
            eq=true
          else log "decision ledger not deterministic for $S"; FAILED+=("determinism-$S"); fi
        else skip "determinism-$S" "decide-repeat-$S failed"; fi
      else skip "decide-repeat-$S" "decide-$S failed"; fi
    else skip "decide-$S" "prerequisite failed (preserve-before=$PB plan=$PLAN_OK tests=$TESTS_OK)"; fi
    DET+=("\"$S\": {\"first\": \"$a\", \"repeat\": \"$b\", \"equal\": $eq}")
  done
  (IFS=,; echo "{${DET[*]}}") > "$HUB/DETERMINISM.json"
  # Evaluator runs only after both ledgers for the study are sealed and byte-identical on repeat.
  for S in V1.24 V1.22; do
    if grep -q "\"$S\": {[^}]*\"equal\": true" "$HUB/DETERMINISM.json" && [ -f "$HUB/decisions/SEAL-$S.json" ]; then
      step "evaluate-$S" run scripts/ig_evaluate.py --study "$S" --decisions "$HUB/decisions" --out "$HUB/results"
    else skip "evaluate-$S" "no sealed deterministic ledger"; fi
  done
  if [ $PB = 1 ]; then
    if step preserve-after run scripts/ig_preserve.py snapshot "$HUB/PRESERVE-AFTER.json"; then
      step preserve-compare run scripts/ig_preserve.py compare "$HUB/PRESERVE-BEFORE.json" "$HUB/PRESERVE-AFTER.json" "$HUB/PRESERVATION.json"
    else skip preserve-compare "preserve-after failed"; fi
  else skip preserve-after "preserve-before failed"; skip preserve-compare "preserve-before failed"; fi
  EL=$(( $(date +%s) - T0 ))
  echo "{\"status\": \"$([ ${#FAILED[@]} = 0 ] && echo STAGES_COMPLETE || echo STAGES_FAILED)\", \"failed_steps\": $(jstr "${FAILED[@]}"), \"any_step_failed\": $([ ${#FAILED[@]} = 0 ] && echo false || echo true), \"seconds_before_report\": $EL, \"seconds\": $EL, \"cap_seconds\": $CAP, \"within_cap\": $([ $EL -le $CAP ] && echo true || echo false), \"commit\": \"$COMMIT\", \"note\": \"whole-run total incl. report is in TERMINAL.json\"}" > "$HUB/RUNTIME.json"
  step report run scripts/ig_report.py --hub "$HUB"
  log "DONE stages elapsed=$(( $(date +%s) - T0 ))s failed=${#FAILED[@]}"
  [ ${#FAILED[@]} = 0 ] && exit 0 || exit 2
fi

# ------------------------------------------------------------------------------------------------ outer driver
HUB="${1:?results hub path}"
CAP=$CAP_MAX; TIGHT=false
if [ -n "${IGUARD_CAP_SECONDS+x}" ]; then
  case "$IGUARD_CAP_SECONDS" in ''|*[!0-9]*) echo "refusing: IGUARD_CAP_SECONDS must be an integer 1..$CAP_MAX"; exit 1;; esac
  if [ "$IGUARD_CAP_SECONDS" -lt 1 ] || [ "$IGUARD_CAP_SECONDS" -gt $CAP_MAX ]; then
    echo "refusing: IGUARD_CAP_SECONDS may only tighten the ${CAP_MAX}s cap (1..$CAP_MAX)"; exit 1
  fi
  CAP=$IGUARD_CAP_SECONDS; [ "$CAP" -lt $CAP_MAX ] && TIGHT=true
fi
T0=$(date +%s); DEADLINE=$((T0 + CAP))
if [ -e "$HUB" ] || [ -L "$HUB" ]; then echo "refusing: $HUB exists"; exit 1; fi
cd "$U" || exit 1
if [ -n "$(git status --porcelain)" ]; then echo "refusing: utility has uncommitted changes"; exit 1; fi
COMMIT=$(git rev-parse HEAD)
mkdir -p "$HUB"/{decisions,decisions-repeat,results,controls,tests} || exit 1
HUB="$(cd "$HUB" && pwd)"
olog() { echo "[$(date +%H:%M:%S)] $*" | tee -a "$HUB/replay.log"; }
TOKEN="iguard-$$-$T0-$RANDOM$RANDOM"
token_pids() {   # every live process (host or container) started by this run
  local e p
  for e in /proc/[0-9]*/environ; do
    p=${e#/proc/}; p=${p%/environ}
    [ "$p" = $$ ] && continue
    tr '\0' '\n' < "$e" 2>/dev/null | grep -qx "IGUARD_RUN_TOKEN=$TOKEN" && echo "$p"
  done 2>/dev/null
}
sweep() {   # terminate leftovers: TERM, grace, KILL. Echoes the number of processes that had to be signalled.
  local pids n=0 i
  pids=$(token_pids); [ -z "$pids" ] && { echo 0; return; }
  n=$(echo "$pids" | wc -l); kill -TERM $pids 2>/dev/null
  for i in $(seq 1 $((KILL_GRACE * 10))); do [ -z "$(token_pids)" ] && break; sleep 0.1; done
  pids=$(token_pids); [ -n "$pids" ] && kill -KILL $pids 2>/dev/null
  echo "$n"
}

finalize() {   # $1 terminal kind, $2 exit code
  local kind="$1" rc="$2" swept within=true el
  swept=$(sweep); el=$(( $(date +%s) - T0 ))
  [ $el -le $CAP ] || within=false
  if [ "$kind" = COMPLETED ] && [ $within = false ]; then kind=TIMEOUT; rc=124; fi
  echo "{\"terminal\": \"$kind\", \"exit_code\": $rc, \"seconds\": $el, \"cap_seconds\": $CAP, \"cap_max_seconds\": $CAP_MAX, \"cap_tightened_for_test\": $TIGHT, \"within_cap\": $within, \"leftover_processes_terminated\": $swept, \"remaining_run_processes\": $(token_pids | wc -l), \"commit\": \"$COMMIT\"}" > "$HUB/TERMINAL.json"
  local supersede=false
  if [ "$kind" != COMPLETED ]; then supersede=true
  elif [ "$rc" != 0 ] && ! grep -q '"technically_complete": false' "$HUB/READINESS.json" 2>/dev/null; then
    supersede=true; kind=FAILED   # a stage failed but no trustworthy INCOMPLETE report was produced
  fi
  if [ $supersede = true ]; then
    local f
    for f in READINESS.json RUNTIME.json RUN-STATUS.md REPORT.md READER-TAKEAWAY.md CLAIM-EVIDENCE.md; do
      [ -e "$HUB/$f" ] && mv -f "$HUB/$f" "$HUB/$f.superseded-by-$kind"
    done
    echo "{\"status\": \"$kind\", \"any_step_failed\": true, \"seconds\": $el, \"cap_seconds\": $CAP, \"within_cap\": $within, \"commit\": \"$COMMIT\"}" > "$HUB/RUNTIME.json"
    echo "{\"technically_complete\": false, \"ready_for_further_consideration\": false, \"terminal\": \"$kind\", \"exit_code\": $rc, \"meaning\": \"run terminated before a trustworthy report; no readiness may be inferred\"}" > "$HUB/READINESS.json"
    printf '# Run status\n\n**INCOMPLETE / PROTOTYPE NOT READY — run %s (exit %s after %ss, cap %ss).**\n\nCodex review: pending. No next stage started.\n' "$kind" "$rc" "$el" "$CAP" > "$HUB/RUN-STATUS.md"
    { printf '# Identity-guard replay (IGUARD-v0.1): %s\n\n' "$kind"
      printf '**Status: INCOMPLETE / PROTOTYPE NOT READY.** The run ended with %s (exit %s) after %ss against a %ss whole-run cap; all stage processes were terminated. No outcome in this hub may be read as a readiness result. Earlier partial files are kept as `*.superseded-by-%s`.\n\n## Stage log (tail)\n\n```\n' "$kind" "$rc" "$el" "$CAP" "$kind"
      tail -n 40 "$HUB/replay.log" 2>/dev/null; printf '```\n'; } > "$HUB/REPORT.md"
  fi
  olog "TERMINAL $kind exit=$rc elapsed=${el}s cap=${CAP}s"
  exit "$rc"
}

olog "START commit=$COMMIT cap=${CAP}s$([ $TIGHT = true ] && echo ' (tightened for test)')"
REM=$((DEADLINE - $(date +%s))); [ $REM -ge 1 ] || REM=1
IGUARD_RUN_TOKEN="$TOKEN" IGUARD_INNER_OK=1 IGUARD_COMMIT="$COMMIT" IGUARD_DEADLINE="$DEADLINE" IGUARD_CAP="$CAP" IGUARD_T0="$T0" \
  timeout --kill-after="$KILL_GRACE" "$REM" "$U/run_replay.sh" --inner "$HUB" &
TPID=$!
on_signal() {
  trap '' INT TERM HUP
  olog "interrupted: terminating stage processes"
  kill -TERM "$TPID" 2>/dev/null   # timeout forwards the signal to the whole stage process group
  local i; for i in $(seq 1 $((KILL_GRACE * 10))); do kill -0 "$TPID" 2>/dev/null || break; sleep 0.1; done
  kill -KILL "$TPID" 2>/dev/null
  wait "$TPID" 2>/dev/null
  finalize INTERRUPTED 130
}
trap on_signal INT TERM HUP
wait "$TPID"; RC=$?
case "$RC" in
  0) finalize COMPLETED 0 ;;
  124|137) olog "whole-run cap ${CAP}s reached: stage processes terminated"; finalize TIMEOUT 124 ;;
  *) finalize COMPLETED 2 ;;
esac
