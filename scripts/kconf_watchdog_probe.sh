#!/bin/bash
# CPU-only probe of the in-container stage watchdog, in the same form the driver uses:
#   distrobox enter dream-research -- unshare -rn bash -c "timeout -k K T <child>"
# The child is a busy CPU loop that writes its PID and never exits. Pass iff timeout returns 124 (or 137 after -k)
# within T+K+slack seconds and the child PID no longer exists afterwards. Usage: kconf_watchdog_probe.sh OUTFILE
OUT=$1; T=5; K=3
PIDF=$(mktemp -p ${DREAM_RUNS:-$HOME/DREAM/Runs} probe-pid.XXXX)
START=$(date +%s)
distrobox enter dream-research -- unshare -rn bash -c "timeout -k $K $T ${DREAM_PY:-python} -c 'import os;open(\"$PIDF\",\"w\").write(str(os.getpid()));exec(\"while True: pass\")'"
RC=$?
END=$(date +%s)
sleep 1
CPID=$(cat $PIDF 2>/dev/null)
ALIVE=$(distrobox enter dream-research -- bash -c "kill -0 $CPID 2>/dev/null && echo alive || echo gone")
rm -f $PIDF
EL=$((END-START))
PASS=no; { [ $RC = 124 ] || [ $RC = 137 ]; } && [ "$ALIVE" = gone ] && [ $EL -le $((T+K+30)) ] && PASS=yes
echo "{\"timeout_s\": $T, \"kill_after_s\": $K, \"rc\": $RC, \"elapsed_s\": $EL, \"child_after\": \"$ALIVE\", \"pass\": \"$PASS\", \"at\": \"$(date -Is)\"}" | tee $OUT
