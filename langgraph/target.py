"""The program under test: a LangGraph Functional API workflow with one side-effecting
@task followed by an approval interrupt.

Every real effect is appended to a tool-side ledger (LEDGER). The fault schedule comes
from CRASH:
  ""                      no fault
  "in_task"               kill the process inside the task, after the effect
  "after_task:<ms>"       kill the process <ms> after the task has returned
  "raise_after_task"      raise after the task has returned

WRITE_DELAY_MS holds every pending write for that long before it reaches SQLite. It
widens a window that exists without it, so the outcome no longer depends on how fast
the host is.
"""

import json
import os
import sys
import time

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.func import entrypoint, task
from langgraph.types import Command, interrupt

LEDGER = os.environ.get("LEDGER", "ledger.jsonl")
CRASH = os.environ.get("CRASH", "")
DURABILITY = os.environ.get("DURABILITY", "sync")  # exit | async | sync
DB = os.environ.get("DB", "checkpoints.sqlite")
THREAD = os.environ.get("THREAD", "t1")
ATTEMPT = int(os.environ.get("ATTEMPT", "1"))  # which process invocation this is
STEP = os.environ.get("STEP", "email_7")
WRITE_DELAY_MS = int(os.environ.get("WRITE_DELAY_MS", "0"))

if WRITE_DELAY_MS:
    _put_writes = SqliteSaver.put_writes

    def _delayed_put_writes(self, config, writes, task_id, task_path=""):
        time.sleep(WRITE_DELAY_MS / 1000)
        return _put_writes(self, config, writes, task_id, task_path)

    SqliteSaver.put_writes = _delayed_put_writes


def ledger(event):
    with open(LEDGER, "a") as f:
        f.write(json.dumps({"ts": time.time(), "event": event, "step": STEP, "attempt": ATTEMPT}) + "\n")


@task
def send_email(step: str) -> str:
    ledger("effect")  # the real, non-idempotent side effect
    if CRASH == "in_task":
        os._exit(137)
    return "sent:" + step


def main(mode):
    with SqliteSaver.from_conn_string(DB) as checkpointer:

        @entrypoint(checkpointer=checkpointer)
        def workflow(inp: dict) -> dict:
            result = send_email(STEP).result()  # the task has finished here
            if CRASH.startswith("after_task:"):
                time.sleep(int(CRASH.split(":")[1]) / 1000)
                os._exit(137)  # die before the entrypoint step is checkpointed
            if CRASH == "raise_after_task":
                raise RuntimeError("simulated failure after the task")
            approved = interrupt({"approve": STEP})
            return {"result": result, "approved": approved}

        inputs = {"start": {"step": STEP}, "resume_crash": None, "resume_approve": Command(resume=True)}
        config = {"configurable": {"thread_id": THREAD}}
        print("OUT", workflow.invoke(inputs[mode], config, durability=DURABILITY))


if __name__ == "__main__":
    main(sys.argv[1])
