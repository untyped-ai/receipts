#!/bin/sh
# usage: ./driver.sh <run_id> <crash-spec> [durability]
# Runs target.py under the fault schedule, resumes it once, and exports the run.
# Output goes to $OUT (default: out/). WRITE_DELAY_MS applies to attempt 1 only.
set -u
RUN=$1; CRASH_SPEC=$2; DUR=${3:-sync}
PY=${PY:-.venv/bin/python}
OUT=${OUT:-out}
STEP=${STEP:-email_7}
DELAY=${WRITE_DELAY_MS:-0}
export STEP
mkdir -p "$OUT"
rm -f "$OUT/$RUN".*

# Did the task's return value reach the checkpointer?
persisted() {
  "$PY" - "$OUT/$RUN.sqlite" <<'EOPY'
import sqlite3, sys
try:
    db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    n = db.execute("select count(*) from writes where channel = '__return__'").fetchone()[0]
except sqlite3.Error:
    n = 0
print("true" if n else "false")
EOPY
}
effects() {
  if [ -f "$OUT/$RUN.ledger.jsonl" ]; then wc -l <"$OUT/$RUN.ledger.jsonl" | tr -d ' '; else echo 0; fi
}

# Attempt 1: start under the fault schedule.
LEDGER=$OUT/$RUN.ledger.jsonl DB=$OUT/$RUN.sqlite ATTEMPT=1 DURABILITY=$DUR CRASH=$CRASH_SPEC \
  WRITE_DELAY_MS=$DELAY "$PY" target.py start >"$OUT/$RUN.a1.out" 2>&1
rc=$?
printf '{"run_id":"%s","step":"%s","attempt":1,"exit":%d,"return_persisted":%s,"crash":"%s","durability":"%s","write_delay_ms":%d}\n' \
  "$RUN" "$STEP" "$rc" "$(persisted)" "$CRASH_SPEC" "$DUR" "$DELAY" >>"$OUT/$RUN.invocations.jsonl"

# Attempt 2: resume, no fault.
before=$(effects)
LEDGER=$OUT/$RUN.ledger.jsonl DB=$OUT/$RUN.sqlite ATTEMPT=2 DURABILITY=$DUR CRASH='' \
  WRITE_DELAY_MS=0 "$PY" target.py resume_crash >"$OUT/$RUN.a2.out" 2>&1
rc=$?
after=$(effects)
replayed=$([ "$after" -eq "$before" ] && echo true || echo false)
printf '{"run_id":"%s","step":"%s","attempt":2,"exit":%d,"return_persisted":%s,"task_replayed":%s}\n' \
  "$RUN" "$STEP" "$rc" "$(persisted)" "$replayed" >>"$OUT/$RUN.invocations.jsonl"

"$PY" export_langgraph.py "$OUT/$RUN.ledger.jsonl" "$OUT/$RUN.invocations.jsonl" "$OUT/$RUN.jsonl"
echo "$RUN crash=$CRASH_SPEC durability=$DUR write_delay_ms=$DELAY effects=$after"
