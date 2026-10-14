import argparse, sys
from .store import load_run, list_runs
from .report import render_text, render_html
from .diff import diff_runs
import json

def main(argv=None):
    p = argparse.ArgumentParser(prog="brilliant-agent")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ls").add_argument("--dir")
    r = sub.add_parser("report"); r.add_argument("file"); r.add_argument("--html")
    d = sub.add_parser("diff"); d.add_argument("a"); d.add_argument("b")
    e = sub.add_parser("export"); e.add_argument("file")
    a = p.parse_args(argv)
    if a.cmd == "ls":
        for path, s in list_runs(a.dir):
            print("%s  tools=%d fail=%d cost=$%.4f  %s" % (
                path, s["tool_calls"], s["tool_failures"], s["cost"], s["goal"]))
    elif a.cmd == "diff":
        print(diff_runs(load_run(a.a), load_run(a.b))[1])
    elif a.cmd == "export":
        print(json.dumps(load_run(a.file), indent=2))
    else:
        ev = load_run(a.file)
        print(render_text(ev))
        if a.html:
            open(a.html, "w", encoding="utf-8").write(render_html(ev))
            print("\nWrote", a.html)
    return 0

if __name__ == "__main__":
    sys.exit(main())
