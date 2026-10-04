# LangGraph: a finished `@task` runs again on resume

A reproduction for
[langchain-ai/langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039)
(reported by @sajjadanwar0): under `durability="sync"`, a `@task` that has already
returned can run again on resume.

```sh
git clone https://github.com/untyped-ai/receipts && cd receipts/langgraph
make repro      # needs Python 3 and Java 11+
make control
```

The first run builds `.venv` from `requirements.lock.txt`. Output goes to `out/`.
The table shows the runs committed in `runs/`, made on the machine listed below.

| Run | Fault | Effects in the tool-side ledger | Verdict |
| --- | --- | --- | --- |
| `kill0` | kill 0 ms after the task returned | 2 | violated (`AtMostOnce`) |
| `kill10` | kill 10 ms after | 1 | accepted |
| `kill50-write200` | kill 50 ms after, the task's pending write held for 200 ms | 2 | violated (`AtMostOnce`) |
| `kill500-write200` | kill 500 ms after, the task's pending write held for 200 ms | 1 | accepted |

`kill0` and `kill10` are the race as it happens: the process dies before or after
the task's pending write reaches SQLite. On the macOS machine below, `kill0` duplicates the effect
in 5 runs out of 5, on langgraph 1.2.11 (pinned here) and on 1.2.12. In a Linux
container on the same machine (Python 3.12, Java 21) it duplicated the effect in 0 runs
out of 10: there the write wins the race. That is the host dependence #8039 reports.

The last two runs hold every pending write for 200 ms before it reaches SQLite. This
is the technique of the `writes-delay` and `put-delay` modes of `probe_race.py` in the
issue. What this folder adds is the run on 1.2.12, the macOS and Linux numbers, and a
TLA+ verdict for each run. The effect is duplicated exactly when the process dies
before the write lands. In
`make repro` (the `kill50-write200` schedule) the process dies at least 150 ms before
the write can land, and in `make control` (the `kill500-write200` schedule) about
300 ms after it, so neither verdict depends on how fast the host is within those
margins. In the Linux container `make repro` duplicated the effect in 5 runs out of 5
and `make control` in 0 runs out of 5. The delay widens a window that exists without
it, as `kill0` shows on macOS.
`make natural` runs `kill0` without the delay, and `make schedules` runs the natural
race at 0, 1, 10, 100 and 1000 ms.

The [Functional API docs](https://docs.langchain.com/oss/python/langgraph/functional-api)
say: "Encapsulate side effects (e.g., writing to a file, sending an email) in tasks to
ensure they are not executed multiple times when resuming a workflow." They also say:
"A task that started but did not finish may run again on that resume, so design side
effects to be idempotent." Here the task had finished. Its effect happened and
`.result()` returned before the process died. As far as I can read the 1.2.11
source, the task's pending write is submitted to a background executor
(`pregel/_loop.py`, `put_writes`), and `durability="sync"` waits only for the
checkpoint write (`pregel/main.py`). That is the ordering issue #8039 describes.

Environment for the committed runs: langgraph 1.2.11, langgraph-checkpoint 4.2.0,
langgraph-checkpoint-sqlite 3.1.1, Python 3.14.7 arm64, macOS 26.6.2, Apple M4.

## What is here

- `target.py`: the program under test. One `@task` with a non-idempotent effect
  written to a ledger, then an approval `interrupt`, with `SqliteSaver`.
- `driver.sh`: runs it under the fault schedule, resumes it once, records whether
  the task's return value reached the checkpointer, and exports the run.
- `export_langgraph.py`: turns the ledger and the driver's record into one JSONL run.
- `spec/`: the TLA+ model the run is checked against, copied unmodified from
  [untyped-ai/untyped](https://github.com/untyped-ai/untyped).
- `runs/`: the runs behind the table. For each run, the ledger, the driver's record,
  the exported run and TLC's output.

## How a run maps to the model

Each process invocation is one `Call`. If the ledger has an effect for that
invocation and the return value was persisted, the call ends in `Ack`. If the effect
happened but the return value was not persisted, it ends in `LostAck`. If the result
was replayed from the checkpoint, there is no `Call` at all. The run is checked with
`KeyMode = "none"`, because a LangGraph task carries no idempotency key.

MIT, see [LICENSE](../LICENSE).
