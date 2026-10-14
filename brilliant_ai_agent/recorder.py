import contextvars, functools, json, os, time, uuid, traceback

from .store import default_dir

_current = contextvars.ContextVar("brilliant_ai_agent_run", default=None)

# USD per 1M tokens (input, output). User-supplied; no built-in prices to go stale.
class ReplayError(Exception):
    """Raised when a replayed run calls a tool the recording did not."""

class ReplayedToolError(Exception):
    """A tool failure reproduced from a recording."""

def _jsonable(v):
    try:
        json.dumps(v)
        return v
    except Exception:
        return None

class Run:
    """Record one agent run to <dir>/<run_id>.jsonl. Every event is flushed
    immediately, so a crash still leaves a readable trace."""

    def __init__(self, goal, directory=None, prices=None, check=None, meta=None,
                 replay_from=None):
        self.goal = goal
        self._replay = None
        if replay_from:
            from .store import load_run
            self._replay = [e for e in load_run(replay_from) if e.get("kind") == "tool"]
            meta = dict(meta or {}, replay_of=replay_from)
        self.prices = prices or {}   # {"model": (in_per_1M, out_per_1M)}
        self.check = check           # optional fn(result) -> bool
        self.run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        d = directory or default_dir()
        os.makedirs(d, exist_ok=True)
        self.path = os.path.join(d, self.run_id + ".jsonl")
        self._f = open(self.path, "a", encoding="utf-8")
        self._seq = 0
        self._token = None
        self.result = None
        self.achieved = None
        self.emit("run_start", goal=goal, meta=meta or {})

    def emit(self, kind, **data):
        self._seq += 1
        ev = {"seq": self._seq, "t": time.time(), "kind": kind, **data}
        self._f.write(json.dumps(ev, default=repr) + "\n")
        self._f.flush()
        return ev

    def llm(self, model, input_tokens=0, output_tokens=0, note=None, error=None):
        cost = None
        if model in self.prices:
            pi, po = self.prices[model]
            cost = (input_tokens * pi + output_tokens * po) / 1e6
        self.emit("llm", model=model, input_tokens=input_tokens,
                  output_tokens=output_tokens, cost=cost, note=note, error=error)

    def _replay_call(self, label, args, t0):
        if not self._replay:
            raise ReplayError("recording has no more tool calls, but %s was called" % label)
        rec = self._replay.pop(0)
        if rec.get("tool") != label:
            raise ReplayError("expected tool %r next, agent called %r" % (rec.get("tool"), label))
        if not rec.get("ok"):
            self.emit("tool", tool=label, args=args, ok=False, error=rec.get("error"),
                      duration=0, replayed=True)
            raise ReplayedToolError(rec.get("error"))
        if rec.get("result_json") is None and rec.get("result") not in (None, "None"):
            raise ReplayError("recorded result of %s was not JSON-serializable; cannot mock" % label)
        self.emit("tool", tool=label, args=args, ok=True, result=rec.get("result"),
                  result_json=rec.get("result_json"), duration=0, replayed=True)
        return rec.get("result_json")

    def set_result(self, result, achieved=None):
        self.result = result
        self.achieved = achieved

    def finish(self, achieved=None, error=None):
        if achieved is None:
            achieved = self.achieved
        if achieved is None and self.check is not None and error is None:
            try:
                achieved = bool(self.check(self.result))
            except Exception as e:
                achieved = False
                error = error or "goal check raised: %r" % (e,)
        self.emit("run_end", achieved=achieved, error=error,
                  result=repr(self.result)[:500])
        self._f.close()

    def __enter__(self):
        self._token = _current.set(self)
        return self

    def __exit__(self, et, ev, tb):
        _current.reset(self._token)
        if et is not None:
            self.finish(achieved=False, error="%s: %s" % (et.__name__, ev))
        else:
            self.finish()
        return False  # never swallow the agent's exception

def current_run():
    return _current.get()

def record_llm(model, input_tokens=0, output_tokens=0, note=None, error=None):
    r = current_run()
    if r:
        r.llm(model, input_tokens, output_tokens, note, error)

def tool(fn=None, *, name=None):
    """Decorator: record each call's args, result or error, and duration."""
    def wrap(f):
        label = name or f.__name__
        @functools.wraps(f)
        def inner(*a, **kw):
            r = current_run()
            if r is None:
                return f(*a, **kw)
            t0 = time.time()
            args = repr((a, kw))[:500]
            if r._replay is not None:
                return r._replay_call(label, args, t0)
            try:
                out = f(*a, **kw)
            except Exception as e:
                r.emit("tool", tool=label, args=args, ok=False,
                       error="%s: %s" % (type(e).__name__, e),
                       duration=time.time() - t0,
                       trace=traceback.format_exc()[-800:])
                raise
            r.emit("tool", tool=label, args=args, ok=True,
                   result=repr(out)[:500], result_json=_jsonable(out),
                   duration=time.time() - t0)
            return out
        return inner
    return wrap(fn) if fn else wrap
