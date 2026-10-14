import os, sys, tempfile, unittest, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from brilliant_ai_agent import Run, tool, record_llm, load_run, summarize, render_text, render_html
from brilliant_ai_agent.cli import main

@tool
def ok_tool(x): return x * 2
@tool
def bad_tool(): raise ValueError("boom")

class T(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp()

    def test_success_and_cost(self):
        with Run("double", directory=self.d, prices={"m": (1.0, 2.0)}, check=lambda r: r == 4) as r:
            r.set_result(ok_tool(2)); record_llm("m", 1_000_000, 500_000)
        s = summarize(load_run(r.path))
        self.assertTrue(s["achieved"]); self.assertEqual(s["tool_calls"], 1)
        self.assertAlmostEqual(s["cost"], 2.0)

    def test_failure_recorded_and_exception_propagates(self):
        with self.assertRaises(ValueError):
            with Run("x", directory=self.d) as r:
                bad_tool()
        s = summarize(load_run(r.path))
        self.assertIs(s["achieved"], False); self.assertEqual(s["tool_failures"], 1)
        self.assertIn("boom", s["first_failure"]["error"])

    def test_goal_not_met(self):
        with Run("x", directory=self.d, check=lambda r: r == 1) as r:
            r.set_result(2)
        self.assertIs(summarize(load_run(r.path))["achieved"], False)

    def test_unknown_goal_when_no_check(self):
        with Run("x", directory=self.d) as r: pass
        self.assertIn("UNKNOWN", render_text(load_run(r.path)))

    def test_loop_detection(self):
        with Run("x", directory=self.d) as r:
            for _ in range(3): ok_tool(1)
        self.assertIn("Loop warning", render_text(load_run(r.path)))

    def test_unpriced_model_marks_partial(self):
        with Run("x", directory=self.d) as r: record_llm("nope", 10, 10)
        self.assertFalse(summarize(load_run(r.path))["cost_known"])

    def test_crash_leaves_incomplete_and_torn_line_ok(self):
        r = Run("x", directory=self.d); ok_tool(1)
        r._f.write('{"seq": 9, "kind": "to'); r._f.flush()  # torn write, never finished
        ev = load_run(r.path)
        self.assertIn("INCOMPLETE", render_text(ev))

    def test_html_escapes(self):
        with Run("<script>", directory=self.d) as r: pass
        h = render_html(load_run(r.path))
        self.assertNotIn("<script>", h); self.assertIn("&lt;script&gt;", h)

    def test_tool_outside_run_is_passthrough(self):
        self.assertEqual(ok_tool(3), 6)

    def test_cli_report(self):
        with Run("x", directory=self.d) as r: ok_tool(1)
        out = os.path.join(self.d, "r.html")
        self.assertEqual(main(["report", r.path, "--html", out]), 0)
        self.assertTrue(os.path.exists(out))

if __name__ == "__main__": unittest.main()

# ---- v0.2: replay, diff, adapters ----
from brilliant_ai_agent import ReplayError, ReplayedToolError, diff_runs, wrap_openai, wrap_anthropic

_calls = []
@tool
def lookup(k):
    _calls.append(k); return {"v": k}
@tool
def flaky():
    raise TimeoutError("slow")

class T2(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp(); _calls.clear()

    def _record(self):
        with Run("g", directory=self.d) as r:
            lookup("a")
            try: flaky()
            except TimeoutError: pass
        return r.path

    def test_replay_mocks_tools_without_calling_them(self):
        rec = self._record(); _calls.clear()
        with Run("g", directory=self.d, replay_from=rec) as r:
            self.assertEqual(lookup("a"), {"v": "a"})
            with self.assertRaises(ReplayedToolError): flaky()
        self.assertEqual(_calls, [])  # real tool never ran

    def test_replay_detects_changed_agent(self):
        rec = self._record()
        with self.assertRaises(ReplayError):
            with Run("g", directory=self.d, replay_from=rec):
                flaky()

    def test_diff_finds_divergence(self):
        a = self._record()
        with Run("g", directory=self.d) as r:
            lookup("a"); lookup("b")
        d, text = diff_runs(load_run(a), load_run(r.path))
        self.assertEqual(d["first_divergence"][0], 2)
        self.assertIn("First divergence", text)

    def test_openai_adapter(self):
        class U: prompt_tokens=10; completion_tokens=5
        class Resp: usage=U(); model="gpt-x"
        class Comp:
            def create(self, **kw): return Resp()
        class Chat: completions=Comp()
        class Client: chat=Chat()
        c = wrap_openai(Client())
        with Run("g", directory=self.d, prices={"gpt-x": (1.0, 1.0)}) as r:
            c.chat.completions.create(model="gpt-x", messages=[])
        s = summarize(load_run(r.path))
        self.assertEqual((s["input_tokens"], s["output_tokens"]), (10, 5))
        self.assertGreater(s["cost"], 0)

    def test_anthropic_adapter_records_error(self):
        class Msgs:
            def create(self, **kw): raise RuntimeError("rate limited")
        class Client: messages=Msgs()
        c = wrap_anthropic(Client())
        with self.assertRaises(RuntimeError):
            with Run("g", directory=self.d) as r:
                c.messages.create(model="claude-x")
        self.assertIn("rate limited", summarize(load_run(r.path))["first_failure"]["error"])

    def test_cli_diff_export(self):
        a = self._record()
        self.assertEqual(main(["diff", a, a]), 0)
        self.assertEqual(main(["export", a]), 0)

# ---- packaging / hygiene ----
import subprocess, shutil
ROOT = os.path.join(os.path.dirname(__file__), "..")

class T3(unittest.TestCase):
    def test_version_matches_pyproject(self):
        import brilliant_ai_agent, re
        t = open(os.path.join(ROOT, "pyproject.toml")).read()
        self.assertEqual(re.search(r'^version = "(.*)"', t, re.M).group(1), brilliant_ai_agent.__version__)

    def test_license_and_contributing_exist(self):
        for f in ("LICENSE", "CONTRIBUTING.md", "README.md"):
            self.assertTrue(os.path.exists(os.path.join(ROOT, f)), f)

    def test_wheel_builds_and_installs_and_cli_runs(self):
        d = tempfile.mkdtemp()
        r = subprocess.run([sys.executable, "-m", "pip", "wheel", ROOT, "--no-deps", "-w", d, "-q"],
                           capture_output=True, text=True)
        if r.returncode != 0 and "No matching distribution" in r.stderr + r.stdout:
            self.skipTest("offline: build backend unavailable")
        self.assertEqual(r.returncode, 0, r.stderr[-500:])
        whl = [f for f in os.listdir(d) if f.endswith(".whl")]
        self.assertEqual(len(whl), 1)
        tgt = os.path.join(d, "site")
        subprocess.run([sys.executable, "-m", "pip", "install", "--no-deps", "-q", "--target", tgt,
                        os.path.join(d, whl[0])], check=True, capture_output=True)
        out = subprocess.run([sys.executable, "-m", "brilliant_ai_agent", "ls", "--dir", d],
                             env=dict(os.environ, PYTHONPATH=tgt), capture_output=True, text=True, cwd=d)
        self.assertEqual(out.returncode, 0, out.stderr)
