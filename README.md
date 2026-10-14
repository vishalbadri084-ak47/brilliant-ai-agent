# Brilliant AI Agent

Flight recorder and replay for AI agents. It records what your agent tried, which tools it called, what failed, what it cost, and whether it met its goal. Everything stays on your machine in a plain JSONL file. No server, no account, no API key, no dependencies.

## 5-minute quick start

Needs Python 3.8+.

```bash
pip install .            # from a clone of this repo
python examples/demo.py  # runs a fake agent that fails on purpose
python -m brilliant_ai_agent ls
python -m brilliant_ai_agent report .brilliant-agent/<run>.jsonl --html report.html
```

Instrument your own agent:

```python
from brilliant_ai_agent import Run, tool, record_llm

@tool
def search(q): ...

with Run("find the pricing page", prices={"my-model": (3.0, 15.0)},   # USD per 1M tokens (in, out)
         check=lambda result: result == "ok") as run:
    record_llm("my-model", input_tokens=900, output_tokens=120)
    run.set_result(search("acme pricing"))
```

The report shows: GOAL MET / NOT MET / UNKNOWN, failed tool calls, the first failure, cost, and a warning when the same tool is called 3+ times with identical arguments.

## Replay and compare

```python
# re-run your agent with tools mocked from a recorded run (real tools never execute)
with Run("same goal", replay_from=".brilliant-agent/<run>.jsonl") as run:
    my_agent()
```

```bash
python -m brilliant_ai_agent diff before.jsonl after.jsonl   # verdict, cost, first divergence
python -m brilliant_ai_agent export run.jsonl                # full JSON
```

Auto-capture of token usage: `wrap_openai(client)` and `wrap_anthropic(client)`.

## Honest limits (v0.2)

- You add `@tool` and `Run` yourself. No automatic framework hooks (LangChain etc.).
- `wrap_openai` and `wrap_anthropic` are tested only against fake clients, not real SDKs. No streaming support. Reports of breakage are welcome.
- Replay mocks tool results only. LLM calls are not replayed. A tool result must be JSON-serializable to be replayed.
- Prices are supplied by you; there is no built-in price table. Models without a price show partial cost.
- Runs store tool arguments and results (truncated to 500 characters). Do not record secrets.
- Not a hosted dashboard. If you need teams, sampling, or evals, look at Langfuse, Arize Phoenix, LangSmith or AgentOps. Similar local tools also exist (for example agent-replay).

## License

MIT. See LICENSE.
