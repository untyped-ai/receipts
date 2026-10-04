# receipts

What agent frameworks actually do under crashes and retries.
One folder per framework: a reproduction in one command, every run checked against
the same TLA+ specification from [untyped-ai/untyped](https://github.com/untyped-ai/untyped).

| Folder | Finding | Related |
| --- | --- | --- |
| [`langgraph/`](langgraph/) | A `@task` that has finished can run again on resume (`durability="sync"`) | [langchain-ai/langgraph#8039](https://github.com/langchain-ai/langgraph/issues/8039) |

MIT.
