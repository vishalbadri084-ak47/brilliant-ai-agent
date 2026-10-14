"""Fake agent: fails a tool, loops, misses its goal. Run: python examples/demo.py"""
from brilliant_ai_agent import Run, tool, record_llm

@tool
def search(q): return ["result for " + q]
@tool
def fetch(url): raise TimeoutError("timed out after 10s")

prices = {"demo-model": (3.0, 15.0)}
with Run("Find the latest pricing page", prices=prices,
         check=lambda r: r == "pricing found") as run:
    record_llm("demo-model", 900, 120)
    search("acme pricing")
    for _ in range(3):
        try: fetch("https://acme.example/pricing")
        except TimeoutError: pass
    record_llm("demo-model", 1500, 80)
    run.set_result("gave up")
print(run.path)
