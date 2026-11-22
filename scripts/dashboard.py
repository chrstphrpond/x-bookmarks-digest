#!/usr/bin/env python3
"""Build a one-page dashboard for x-saves-harvest from what the skill already keeps.

Reads the handled-posts ledger (seen.json) and the notes file the skill writes, and
writes one self-contained HTML file. It reads nothing from X and changes neither file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

SEEN_FILE = Path.home() / ".local/state/x-saves-harvest" / "seen.json"
RUN_EVERY_DAYS = 7

KINDS = ["Skills", "MCP servers", "Repos and tools", "Techniques", "Resources", "Build ideas"]
ICONS = {  # lucide, 24px viewBox, stroke 2
    "Skills": '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/>',
    "MCP servers": '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
    "Repos and tools": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "Techniques": '<path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/>',
    "Resources": '<path d="M12 7v14"/><path d="M3 18a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h5a4 4 0 0 1 4 4 4 4 0 0 1 4-4h5a1 1 0 0 1 1 1v13a1 1 0 0 1-1 1h-6a3 3 0 0 0-3 3 3 3 0 0 0-3-3z"/>',
    "Build ideas": '<path d="m15 12-8.373 8.373a1 1 0 1 1-3-3L12 9"/><path d="m18 15 4-4"/><path d="m21.5 11.5-1.914-1.914A2 2 0 0 1 19 8.172V7l-2.26-2.26a6 6 0 0 0-4.202-1.756L9 2.96l.92.82A6.18 6.18 0 0 1 12 8.4V10l2 2h1.172a2 2 0 0 1 1.414.586L18.5 14.5"/>',
}


def kind_of(heading):
    h = heading.lower()
    for k in KINDS:
        if h.startswith(k.lower().split(" ")[0]):
            return k
    return None


def read_note(path):
    """Entries the skill wrote: one per bullet under a kind heading, inside a dated run."""
    entries, run, kind = [], None, None
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^## (\d{4}-\d{2}-\d{2})\s*$", line)
        if m:
            run, kind = m.group(1), None
            continue
        m = re.match(r"^#{3,4} (.+?)\s*$", line)
        if m:
            kind = kind_of(m.group(1)) or kind if m.group(0).startswith("####") else kind_of(m.group(1))
            continue
        if run and kind and line.startswith("- "):
            body = line[2:]
            link = re.match(r"\[([^\]]+)\]\((https?://[^)]+)\)", body)
            name = link.group(1) if link else re.split(r"[:.]", body, maxsplit=1)[0]
            stars = re.search(r"([\d.]+k?) stars", body)
            entries.append({"run": run, "kind": kind, "name": name.strip()[:70], "url": link.group(2) if link else "",
                            "stars": stars.group(1) if stars else ""})
    return entries


def e(text):
    return html.escape(str(text), quote=True)


def day(text):
    return dt.date.fromisoformat(text)


def build(seen, entries, today):
    runs = sorted(seen.get("runs", []), key=lambda r: r["date"])
    checked = sum(r.get("new", 0) for r in runs)
    ai = sum(r.get("ai", 0) for r in runs)
    kept = len(entries)
    kept_by_run = {}
    for x in entries:
        kept_by_run[x["run"]] = kept_by_run.get(x["run"], 0) + 1
    by_kind = {k: sum(1 for x in entries if x["kind"] == k) for k in KINDS}
    top_kind = max(by_kind.values(), default=0) or 1

    last = day(runs[-1]["date"]) if runs else None
    if last is None:
        due_text, due_cls = "No runs yet", "due late"
    else:
        left = RUN_EVERY_DAYS - (today - last).days
        due_text = f"Next run in {left} day{'s' if left != 1 else ''}" if left > 0 else ("Run due today" if left == 0 else f"Run overdue by {-left} day{'s' if left != -1 else ''}")
        due_cls = "due" if left > 0 else "due late"

    def pct(n, of):
        return f"{(100 * n / of) if of else 0:.2f}%"

    run_rows = []
    for r in reversed(runs):
        n, a, k = r.get("new", 0), r.get("ai", 0), kept_by_run.get(r["date"], 0)
        a, k = min(a, n), min(k, min(a, n))
        d = day(r["date"])
        run_rows.append(f"""
      <li class="run">
        <time datetime="{e(r['date'])}"><b>{d:%d}</b>{d:%b}</time>
        <span class="n">{n}</span>
        <span class="bar" role="img" aria-label="{n} checked, {a} about AI tools, {k} kept">
          <i class="k" style="width:{pct(k, n)}"></i><i class="a" style="width:{pct(a - k, n)}"></i>
        </span>
        <span class="kept">{k}</span>
      </li>""")

    kind_rows = []
    for k in KINDS:
        kind_rows.append(f"""
      <li class="kind">
        <svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[k]}</svg>
        <span class="label">{e(k)}</span>
        <span class="bar"><i class="k" style="width:{pct(by_kind[k], top_kind)}"></i></span>
        <span class="n">{by_kind[k]}</span>
      </li>""")

    newest = sorted(entries, key=lambda x: x["run"], reverse=True)[:8]
    find_rows = []
    for x in newest:
        name = f'<a class="name" href="{e(x["url"])}">{e(x["name"])}</a>' if x["url"] else f'<span class="name">{e(x["name"])}</span>'
        find_rows.append(f"""
      <li class="find">
        <svg viewBox="0 0 24 24" aria-hidden="true">{ICONS[x['kind']]}</svg>
        {name}
        <span class="stars">{e(x['stars']) + ' stars' if x['stars'] else ''}</span>
        <time datetime="{e(x['run'])}">{day(x['run']):%b %d}</time>
      </li>""")
    if not find_rows:
        find_rows.append('<li class="empty">Nothing kept yet. Run the skill once to fill this in.</li>')
    if not run_rows:
        run_rows.append('<li class="empty">No runs recorded yet.</li>')

    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X saves</title>
<style>
:root{{--paper:#f3f0e8;--ink:#1e1c17;--mid:#6f6a5e;--soft:#d9d4c6;--faint:#e7e3d8;--accent:#c8501a}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.45 ui-sans-serif,"Avenir Next","Segoe UI",system-ui,sans-serif;font-variant-numeric:tabular-nums}}
main{{max-width:1040px;margin:0 auto;padding:40px 24px 64px}}
header{{display:flex;justify-content:space-between;align-items:baseline;gap:16px;color:var(--mid);font-size:15px}}
.due.late{{color:var(--accent);font-weight:600}}
h1{{font-size:clamp(40px,7vw,76px);line-height:1.02;font-weight:650;margin:28px 0 20px;max-width:14ch;text-wrap:balance}}
h1 em{{font-style:normal;color:var(--accent)}}
h2{{font-size:15px;font-weight:600;color:var(--mid);margin:0 0 14px}}
.funnel{{display:flex;height:14px;border-radius:7px;overflow:hidden;background:var(--faint)}}
.funnel i,.bar i{{display:block;height:100%}}
.k{{background:var(--ink)}} .a{{background:var(--soft)}}
.funnel .k{{background:var(--accent)}}
.legend{{display:flex;flex-wrap:wrap;gap:6px 28px;margin:12px 0 0;padding:0;list-style:none;color:var(--mid);font-size:15px}}
.legend b{{color:var(--ink);font-weight:600;margin-right:6px}}
.legend i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px}}
.grid{{display:grid;grid-template-columns:1.25fr 1fr;gap:56px;margin-top:64px}}
ul{{list-style:none;margin:0;padding:0}}
.run{{display:grid;grid-template-columns:52px 60px 1fr 32px;align-items:center;gap:14px;min-height:44px}}
.run time{{font-size:13px;color:var(--mid);line-height:1.1}} .run time b{{display:block;font-size:19px;color:var(--ink);font-weight:600}}
.run .n,.kind .n{{text-align:right;color:var(--mid)}}
.run .kept{{text-align:right;font-weight:600}}
.bar{{display:flex;height:10px;border-radius:5px;overflow:hidden;background:var(--faint)}}
.cols{{display:grid;grid-template-columns:52px 60px 1fr 32px;gap:14px;font-size:13px;color:var(--mid);margin-bottom:4px}}
.cols span:nth-child(2),.cols span:nth-child(4){{text-align:right}}
.kind{{display:grid;grid-template-columns:22px 128px 1fr 28px;align-items:center;gap:12px;min-height:44px}}
svg{{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;color:var(--mid);flex:none}}
.finds{{margin-top:64px}}
.find{{display:grid;grid-template-columns:22px 1fr auto 56px;align-items:center;gap:12px;min-height:44px}}
.find .name{{color:var(--ink);font-weight:550;text-decoration:none;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:10px 0}}
.find a.name:hover{{text-decoration:underline}} .find a.name:focus-visible{{outline:2px solid var(--accent);outline-offset:2px}}
.find .stars,.find time{{color:var(--mid);font-size:14px;text-align:right}}
.empty{{color:var(--mid);padding:12px 0}}
@media (max-width:760px){{.grid{{grid-template-columns:1fr;gap:48px}} .find{{grid-template-columns:22px 1fr 56px}} .find .stars{{display:none}} header{{flex-direction:column;gap:2px}}}}
</style>
<main>
  <header><span>X saves, read-only, {len(runs)} run{'s' if len(runs) != 1 else ''}{f', last on {last:%b %d}' if last else ''}</span><span class="{due_cls}">{e(due_text)}</span></header>
  <h1><em>{kept}</em> kept from {checked} saves</h1>
  <div class="funnel" role="img" aria-label="{checked} saves checked, {ai} about AI tools, {kept} kept">
    <i class="k" style="width:{pct(min(kept, ai), checked)}"></i><i class="a" style="width:{pct(max(ai - kept, 0), checked)}"></i>
  </div>
  <ul class="legend">
    <li><i style="background:var(--accent)"></i><b>{kept}</b>kept in notes</li>
    <li><i style="background:var(--soft)"></i><b>{max(ai - kept, 0)}</b>about AI tools, dropped</li>
    <li><i style="background:var(--faint)"></i><b>{checked - ai}</b>off topic</li>
  </ul>

  <div class="grid">
    <section>
      <h2>Each run</h2>
      <div class="cols"><span>Date</span><span>Checked</span><span>Share kept</span><span>Kept</span></div>
      <ul>{''.join(run_rows)}
      </ul>
    </section>
    <section>
      <h2>What was kept</h2>
      <ul>{''.join(kind_rows)}
      </ul>
    </section>
  </div>

  <section class="finds">
    <h2>Newest finds</h2>
    <ul>{''.join(find_rows)}
    </ul>
  </section>
</main>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a one-page HTML dashboard from the handled-posts ledger and the notes file.")
    ap.add_argument("--note", required=True, help="the notes file the skill writes (Markdown)")
    ap.add_argument("--out", required=True, help="HTML file to write")
    ap.add_argument("--seen", default=str(SEEN_FILE), help="handled-posts ledger (default: %(default)s)")
    ap.add_argument("--today", help="count days since the last run from this date (YYYY-MM-DD); default is today")
    a = ap.parse_args(argv)
    try:
        seen = json.loads(Path(a.seen).read_text(encoding="utf-8"))
        entries = read_note(Path(a.note))
        today = day(a.today) if a.today else dt.date.today()
    except (OSError, ValueError) as err:
        print(f"Stopped, nothing written: {err}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(seen, entries, today), encoding="utf-8")
    print(f"{len(entries)} kept entries across {len(seen.get('runs', []))} runs. Dashboard: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
