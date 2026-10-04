"""Turn one LangGraph run into the JSONL format checked by untyped.

Inputs are the tool-side ledger (one line per real effect) and the driver's record
of each process invocation, which includes whether the task's return value reached
the checkpointer.
"""

import json
import sys


def read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def export(ledger_path, invocations_path):
    effects = [e for e in read_jsonl(ledger_path) if e["event"] == "effect"]
    invocations = read_jsonl(invocations_path)
    step = invocations[0]["step"]

    # LangGraph has no tool-call budget and the driver resumes exactly once, so the
    # bounds below are simply what the driver does: only AtMostOnce is under test.
    # The approval interrupt comes after the effect, so no step is gated by it.
    header = {
        "kind": "run",
        "run_id": invocations[0]["run_id"],
        "steps": [step],
        "destructive": [],
        "max_retries": len(invocations) - 1,
        "budget": len(invocations),
        "key_mode": "none",
        "on_approval_timeout": "abort",
        "budget_scope": "run",
    }

    events, total = [header], 0
    for inv in invocations:
        attempt = inv["attempt"]
        if inv.get("task_replayed"):
            # The result was loaded from the checkpoint: the tool was not called.
            continue
        events.append({"event": "Call", "step": step, "attempt": attempt})
        ran = sum(1 for e in effects if e["attempt"] == attempt)
        total += ran
        if ran == 0:
            outcome = "Dropped"
        elif inv["return_persisted"]:
            outcome = "Ack"
        else:
            outcome = "LostAck"
        events.append({"event": outcome, "step": step, "attempt": attempt, "effects": total})
    return events


if __name__ == "__main__":
    ledger, invocations, out = sys.argv[1:4]
    with open(out, "w") as f:
        for event in export(ledger, invocations):
            f.write(json.dumps(event) + "\n")
