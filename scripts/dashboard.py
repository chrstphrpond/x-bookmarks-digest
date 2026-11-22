#!/usr/bin/env python3
"""Build a one-page dashboard for x-bookmarks-digest from what the skill already keeps.

Reads the handled-posts ledger (seen.json) and the notes file the skill writes, and
writes one HTML file. It changes neither file. The page itself asks X for a post only when
the reader presses "Post" on a row, through X's official embedded-post widget.
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

SEEN_FILE = Path.home() / ".local/state/x-bookmarks-digest" / "seen.json"
TRENDING_FILE = SEEN_FILE.with_name("trending.json")
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


UI = {  # lucide
    "home": '<path d="M15 21v-8a1 1 0 0 0-1-1h-4a1 1 0 0 0-1 1v8"/><path d="M3 10a2 2 0 0 1 .709-1.528l7-5.999a2 2 0 0 1 2.582 0l7 5.999A2 2 0 0 1 21 10v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "bookmark": '<path d="m19 21-7-4-7 4V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v16z"/>',
    "layers": '<path d="M12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83z"/><path d="M2 12a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 12"/><path d="M2 17a1 1 0 0 0 .58.91l8.6 3.91a2 2 0 0 0 1.65 0l8.58-3.9A1 1 0 0 0 22 17"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "star": '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>',
    "link": '<path d="M15 3h6v6"/><path d="M10 14 21 3"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
    "post": '<path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/>',
    "heart": '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"/>',
    "eye": '<path d="M2.062 12.348a1 1 0 0 1 0-.696 10.75 10.75 0 0 1 19.876 0 1 1 0 0 1 0 .696 10.75 10.75 0 0 1-19.876 0"/><circle cx="12" cy="12" r="3"/>',
    "flame": '<path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.500 2 1.600 3 3.500 3 5.500a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.500z"/>',
}
TIMELINE = 40  # newest entries shown in the timeline


def icon(paths):
    return f'<svg viewBox="0 0 24 24" aria-hidden="true">{paths}</svg>'


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
            rest = body[link.end():] if link else body
            name = link.group(1) if link else re.split(r"[:.]", body, maxsplit=1)[0]
            if not link:
                rest = body[len(name):]
            stars = re.search(r"([\d.]+k?) stars", body)
            post = re.search(r"\[post\]\((https?://[^)]+)\)", body)
            text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", rest).lstrip(":. ").strip()
            text = re.split(r"\s+[\d.]+k? stars", text)[0]          # facts and the post link come after the description
            text = re.sub(r"\s*\bpost\b\.?\s*$", "", text).strip()
            if len(text) > 200:
                text = text[:200].rsplit(" ", 1)[0] + "…"
            entries.append({"run": run, "kind": kind, "name": name.strip()[:70], "url": link.group(2) if link else "",
                            "stars": stars.group(1) if stars else "", "post": post.group(1) if post else "", "text": text})
    return entries


def short(n):
    """12345 -> 12.3K, the way counts read on X."""
    n = int(n or 0)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n / 1_000:.1f}K".replace(".0K", "K")
    return str(n)


def e(text):
    return html.escape(str(text), quote=True)


def day(text):
    return dt.date.fromisoformat(text)


CSS = """
:root{--bg:#000;--text:#e7e9ea;--dim:#71767b;--line:#2f3336;--card:#16181c;--hover:rgba(231,233,234,.06);--blue:#1d9bf0;--red:#f4212e;--track:#2f3336}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:110px}
body{margin:0;background:var(--bg);color:var(--text);font:15px/20px "Helvetica Neue",Helvetica,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;font-variant-numeric:tabular-nums}
a{color:inherit;text-decoration:none}
svg{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round;flex:none}
ul{list-style:none;margin:0;padding:0}
.app{display:grid;grid-template-columns:260px 600px 350px;gap:0 28px;justify-content:center;align-items:start;max-width:1280px;margin:0 auto}
nav{position:sticky;top:0;height:100vh;padding:8px 12px 16px;display:flex;flex-direction:column;gap:4px}
nav .mark{font-size:20px;font-weight:800;padding:14px 12px 18px}
nav a{display:flex;align-items:center;gap:20px;padding:12px;border-radius:9999px;font-size:20px;line-height:24px;min-height:50px;width:fit-content;padding-right:24px}
nav a:hover{background:var(--hover)} nav a svg{width:26px;height:26px}
nav a:focus-visible,.tabs button:focus-visible,.act a:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.status{margin-top:16px;padding:14px 20px;border-radius:9999px;background:var(--blue);color:#fff;font-weight:700;font-size:17px;text-align:center;width:90%}
.status.late{background:var(--red)}
.who{margin-top:auto;padding:12px;color:var(--dim)} .who b{display:block;color:var(--text)}
main{border-left:1px solid var(--line);border-right:1px solid var(--line);min-height:100vh;min-width:0}
.top{position:sticky;top:0;z-index:2;background:rgba(0,0,0,.72);backdrop-filter:blur(12px);border-bottom:1px solid var(--line)}
.top h1{font-size:20px;line-height:24px;font-weight:700;margin:0;padding:14px 16px 2px}
.top p{margin:0;padding:0 16px 8px;color:var(--dim);font-size:13px;line-height:16px}
.tabs{display:flex;overflow-x:auto;scrollbar-width:none}
.tabs button{flex:1 0 auto;min-height:53px;padding:0 16px;background:none;border:0;color:var(--dim);font:500 15px/20px inherit;font-family:inherit;cursor:pointer;position:relative}
.tabs button:hover{background:var(--hover)}
.tabs button[aria-selected=true]{color:var(--text);font-weight:700}
.tabs button[aria-selected=true]::after{content:"";position:absolute;left:50%;bottom:0;transform:translateX(-50%);width:56px;max-width:70%;height:4px;border-radius:9999px;background:var(--blue)}
.hero{padding:20px 16px 18px;border-bottom:1px solid var(--line)}
.hero .big{font-size:52px;line-height:56px;font-weight:800;margin:0 0 14px;text-wrap:balance}
.hero .big em{font-style:normal;color:var(--blue)}
.bar{display:flex;height:8px;border-radius:9999px;overflow:hidden;background:var(--track)}
.bar i{display:block;height:100%} .bar .k{background:var(--blue)} .bar .a{background:#536471}
.legend{display:flex;flex-wrap:wrap;gap:4px 22px;margin-top:12px;color:var(--dim)}
.legend b{color:var(--text);font-weight:700;margin-right:5px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:9999px;margin-right:7px}
.item{display:grid;grid-template-columns:40px 1fr;gap:12px;padding:12px 16px;border-bottom:1px solid var(--line)}
.item:hover{background:rgba(231,233,234,.03)}
.item[hidden]{display:none}
.av{width:40px;height:40px;border-radius:9999px;background:var(--card);display:grid;place-items:center;color:var(--text)}
.item .hd{display:flex;gap:4px;min-width:0;color:var(--dim)}
.item .name{color:var(--text);font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.item a.name:hover{text-decoration:underline}
.item .hd span{white-space:nowrap}
.item p{margin:2px 0 0;overflow-wrap:anywhere}
.act{display:flex;gap:44px;margin-top:6px;color:var(--dim);font-size:13px}
.act>*{display:inline-flex;align-items:center;gap:6px;min-height:36px} .act svg{width:18px;height:18px}
.act a:hover,.act button:hover{color:var(--blue)}
.act button{background:none;border:0;padding:0;color:inherit;font:inherit;cursor:pointer}
.act button[aria-expanded=true]{color:var(--blue)}
.act button:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.embed{min-height:120px;margin-top:4px} .embed[hidden]{display:none} .embed .twitter-tweet{margin:0!important}
.embed .wait,.embed .fail{color:var(--dim);font-size:13px;padding:12px 0} .embed .fail a{color:var(--blue)}
.empty{padding:32px 16px;color:var(--dim);text-align:center}
.av.t{font-weight:800;font-size:17px}
.item .hd a.when:hover,.item .hd a.handle:hover{text-decoration:underline}
.item p b{font-weight:700}
.card a.trend{text-decoration:none} .trend .line{grid-column:1;font-weight:700;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.trend .meta{grid-column:1;color:var(--dim);font-size:13px;line-height:16px}
aside{position:sticky;top:0;padding:12px 0 24px;display:grid;gap:16px}
.card{background:var(--card);border-radius:16px;overflow:hidden}
.card h2{font-size:20px;line-height:24px;font-weight:800;margin:0;padding:12px 16px}
.trend{display:grid;grid-template-columns:1fr auto;align-items:center;gap:2px 12px;padding:10px 16px;min-height:60px;width:100%;background:none;border:0;color:inherit;font:inherit;text-align:left;cursor:pointer}
.trend:hover{background:rgba(255,255,255,.03)}
.trend small{color:var(--dim);font-size:13px;line-height:16px;grid-column:1} .trend b{grid-column:1;font-weight:700}
.trend .n{grid-row:1/3;grid-column:2;font-size:20px;font-weight:700}
.trend .bar{grid-column:1/3;height:4px;margin-top:6px}
.run{display:grid;grid-template-columns:54px 1fr 34px;align-items:center;gap:12px;padding:8px 16px;min-height:52px}
.run time b{display:block;font-weight:700} .run time{color:var(--dim);font-size:13px;line-height:16px}
.run .mid small{display:block;color:var(--dim);font-size:13px;line-height:16px;margin-bottom:5px}
.run .mid .bar{height:6px} .run .kept{text-align:right;font-weight:700}
.card .foot{padding:10px 16px 14px;color:var(--dim);font-size:13px;line-height:16px}
@media (max-width:1240px){.app{grid-template-columns:76px 600px 350px} nav .mark,nav a span,.who,.status{display:none} nav a{padding:12px}}
@media (max-width:1060px){.app{grid-template-columns:76px minmax(0,600px)} aside{grid-column:2;position:static;padding:16px 0 32px}}
@media (max-width:700px){.app{grid-template-columns:minmax(0,1fr)} nav{display:none} aside{grid-column:1;padding:16px 12px 32px} main{border:0} .hero .big{font-size:38px;line-height:42px} .act{gap:28px}}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

JS = """
const tabs=[...document.querySelectorAll('.tabs button')],items=[...document.querySelectorAll('.item')],none=document.querySelector('.empty.filter');
function pick(kind){tabs.forEach(b=>{b.setAttribute('aria-selected',String(b.dataset.kind===kind));if(b.dataset.kind===kind)b.scrollIntoView({inline:'nearest',block:'nearest'})});let n=0;
items.forEach(i=>{const on=kind==='All'?i.dataset.kind!=='Trending':i.dataset.kind===kind;i.hidden=!on;if(on)n++});none.hidden=n>0}
tabs.forEach(b=>b.addEventListener('click',()=>pick(b.dataset.kind)));
let widgets;
function loadWidgets(){return widgets||(widgets=new Promise((ok,no)=>{const t=window.twttr=window.twttr||{};t._e=t._e||[];t.ready=t.ready||(f=>t._e.push(f));
const s=document.createElement('script');s.src='https://platform.twitter.com/widgets.js';s.async=true;s.onerror=no;document.head.appendChild(s);
t.ready(ok);setTimeout(no,15000)}))}
document.querySelectorAll('.show').forEach(b=>b.addEventListener('click',()=>{const box=b.closest('.item').querySelector('.embed'),open=b.getAttribute('aria-expanded')==='true';
b.setAttribute('aria-expanded',String(!open));box.hidden=open;if(open||box.dataset.done)return;box.dataset.done='1';box.innerHTML='<div class="wait">Loading the post from X</div>';
const fail=()=>{box.innerHTML='<div class="fail">X did not return this post. <a href="'+b.dataset.url+'">Open it on X</a></div>'};
loadWidgets().then(t=>t.widgets.createTweet(b.dataset.post,box,{theme:'dark',dnt:true,conversation:'none'})).then(el=>{const w=box.querySelector('.wait');if(w)w.remove();if(!el)fail()}).catch(fail)}));
document.querySelectorAll('button.trend').forEach(t=>t.addEventListener('click',()=>{pick(t.dataset.kind);document.getElementById('finds').scrollIntoView()}));
"""


def build(seen, entries, today, trending=None):
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
        due_text, late = "No runs yet", True
    else:
        left = RUN_EVERY_DAYS - (today - last).days
        due_text = f"Next run in {left} day{'s' if left != 1 else ''}" if left > 0 else ("Run due today" if left == 0 else f"Overdue by {-left} day{'s' if left != -1 else ''}")
        late = left <= 0

    def pct(n, of):
        return f"{(100 * n / of) if of else 0:.2f}%"

    topics = [tp for tp in (trending or {}).get("topics", []) if tp.get("posts")]
    tab_names = ["All"] + KINDS + (["Trending"] if topics else [])
    tabs = "".join(f'<button role="tab" data-kind="{e(k)}" aria-selected="{"true" if k == "All" else "false"}">{e(k)}</button>' for k in tab_names)

    def when(text):
        try:
            return f"{dt.datetime.fromisoformat(text.replace('Z', '+00:00')):%b %d}"
        except ValueError:
            return ""

    hot_items, hot_card = [], ""
    for tp in topics:
        for x in tp["posts"]:
            body = f'<b>{e(x["article"])}</b>' if x.get("article") else e(x["text"])
            hot_items.append(f"""
      <li class="item" data-kind="Trending" hidden>
        <span class="av t" title="{e(tp['name'])}">{e(tp['name'][:1])}</span>
        <div>
          <div class="hd"><span class="name">{e(x['name'])}</span><a class="handle" href="https://x.com/{e(x['handle'])}">@{e(x['handle'])}</a><span>·</span><a class="when" href="{e(x['url'])}">{when(x['time'])}</a></div>
          <p>{body}</p>
          <div class="act"><span>{icon(UI['heart'])}{short(x['likes'])}</span><span>{icon(UI['eye'])}{short(x['views'])}</span><span>{e(tp['name'])}{' · Article' if x.get('article') else ''}</span><button class="show" data-post="{e(x['id'])}" data-url="{e(x['url'])}" aria-expanded="false">{icon(UI['post'])}Post</button></div>
          <div class="embed" hidden></div>
        </div>
      </li>""")
    if topics:
        rows = "".join(f"""
      <a class="trend" href="{e(x['url'])}">
        <small>{e(tp['name'])} · Trending</small><span class="line">{e(x.get('article') or x['text'][:110])}</span>
        <span class="meta">{short(x['likes'])} likes · @{e(x['handle'])}</span>
      </a>""" for tp in topics for x in tp["posts"][:2])
        read = when(trending.get("collected_at", ""))
        days = trending.get("days")
        hot_card = f"""
    <section class="card" id="trending">
      <h2>Trending now</h2>{rows}
      <div class="foot">Most liked posts on X{f' in the last {days} days' if days else ''}{f', read {read}' if read else ''}. These are not saves.</div>
    </section>"""

    items = []
    for x in sorted(entries, key=lambda x: x["run"], reverse=True)[:TIMELINE]:
        name = f'<a class="name" href="{e(x["url"])}">{e(x["name"])}</a>' if x["url"] else f'<span class="name">{e(x["name"])}</span>'
        acts = [f'<span>{icon(UI["star"])}{e(x["stars"])}</span>'] if x["stars"] else []
        pid = None
        if x["url"]:
            acts.append(f'<a href="{e(x["url"])}">{icon(UI["link"])}Repo</a>')
        pid = re.search(r"/status/(\d+)", x["post"])
        if pid:
            acts.append(f'<button class="show" data-post="{pid.group(1)}" data-url="{e(x["post"])}" aria-expanded="false">{icon(UI["post"])}Post</button>')
        elif x["post"]:
            acts.append(f'<a href="{e(x["post"])}">{icon(UI["post"])}Post</a>')
        items.append(f"""
      <li class="item" data-kind="{e(x['kind'])}">
        <span class="av">{icon(ICONS[x['kind']])}</span>
        <div>
          <div class="hd">{name}<span>{e(x['kind'])}</span><span>·</span><span><time datetime="{e(x['run'])}">{day(x['run']):%b %d}</time></span></div>
          {f'<p>{e(x["text"])}</p>' if x['text'] else ''}
          {f'<div class="act">{"".join(acts)}</div>' if acts else ''}
          {'<div class="embed" hidden></div>' if pid else ''}
        </div>
      </li>""")
    if not items:
        items.append('<li class="empty">Nothing kept yet. Run the skill once to fill this in.</li>')
    items += hot_items

    trends = "".join(f"""
      <button class="trend" data-kind="{e(k)}">
        <small>Kind</small><b>{e(k)}</b><span class="n">{by_kind[k]}</span>
        <span class="bar"><i class="k" style="width:{pct(by_kind[k], top_kind)}"></i></span>
      </button>""" for k in KINDS)

    run_rows = []
    for r in reversed(runs):
        n, a = r.get("new", 0), r.get("ai", 0)
        a = min(a, n)
        k = min(kept_by_run.get(r["date"], 0), a)
        d = day(r["date"])
        run_rows.append(f"""
      <li class="run">
        <time datetime="{e(r['date'])}"><b>{d:%b %d}</b>{d:%Y}</time>
        <span class="mid"><small>{n} checked</small><span class="bar" role="img" aria-label="{n} checked, {a} about AI tools, {k} kept"><i class="k" style="width:{pct(k, n)}"></i><i class="a" style="width:{pct(a - k, n)}"></i></span></span>
        <span class="kept">{k}</span>
      </li>""")
    if not run_rows:
        run_rows.append('<li class="empty">No runs recorded yet.</li>')

    shown = min(kept, TIMELINE)
    return f"""<!doctype html>
<html lang="en">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>X saves</title>
<style>{CSS}</style>
<div class="app" id="top">
  <nav aria-label="Sections">
    <div class="mark">x-bookmarks</div>
    <a href="#top">{icon(UI['home'])}<span>Overview</span></a>
    <a href="#finds">{icon(UI['bookmark'])}<span>Finds</span></a>
    <a href="#kinds">{icon(UI['layers'])}<span>Kinds</span></a>
    <a href="#runs">{icon(UI['clock'])}<span>Runs</span></a>
    {f'<a href="#trending">{icon(UI["flame"])}<span>Trending</span></a>' if topics else ''}
    <div class="status{' late' if late else ''}">{e(due_text)}</div>
    <div class="who"><b>x-bookmarks-digest</b>Read-only, weekly</div>
  </nav>

  <main>
    <div class="top">
      <h1>Saves</h1>
      <p>{len(runs)} run{'s' if len(runs) != 1 else ''}{f', last on {last:%b %d}' if last else ''}</p>
      <div class="tabs" role="tablist" aria-label="Kind">{tabs}</div>
    </div>
    <section class="hero">
      <p class="big"><em>{kept}</em> kept from {checked} saves</p>
      <div class="bar" role="img" aria-label="{checked} saves checked, {ai} about AI tools, {kept} kept">
        <i class="k" style="width:{pct(min(kept, ai), checked)}"></i><i class="a" style="width:{pct(max(ai - kept, 0), checked)}"></i>
      </div>
      <div class="legend">
        <span><i style="background:var(--blue)"></i><b>{kept}</b>kept</span>
        <span><i style="background:#536471"></i><b>{max(ai - kept, 0)}</b>AI tools, dropped</span>
        <span><i style="background:var(--track)"></i><b>{checked - ai}</b>off topic</span>
      </div>
    </section>
    <ul id="finds" aria-label="Newest {shown} of {kept} kept">{''.join(items)}
      <li class="empty filter" hidden>None of the newest {shown} are this kind.</li>
    </ul>
  </main>

  <aside>{hot_card}
    <section class="card" id="kinds">
      <h2>What was kept</h2>{trends}
    </section>
    <section class="card" id="runs">
      <h2>Each run</h2>
      <ul>{''.join(run_rows)}
      </ul>
      <div class="foot">Blue is the share kept. Grey is about AI tools but dropped.</div>
    </section>
  </aside>
</div>
<script>{JS}</script>
</html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write a one-page HTML dashboard from the handled-posts ledger and the notes file.")
    ap.add_argument("--note", required=True, help="the notes file the skill writes (Markdown)")
    ap.add_argument("--out", required=True, help="HTML file to write")
    ap.add_argument("--seen", default=str(SEEN_FILE), help="handled-posts ledger (default: %(default)s)")
    ap.add_argument("--trending", default=str(TRENDING_FILE), help="trending posts from `xsaves.py trending`, if any (default: %(default)s)")
    ap.add_argument("--today", help="count days since the last run from this date (YYYY-MM-DD); default is today")
    a = ap.parse_args(argv)
    try:
        seen = json.loads(Path(a.seen).read_text(encoding="utf-8"))
        entries = read_note(Path(a.note))
        today = day(a.today) if a.today else dt.date.today()
        hot = json.loads(Path(a.trending).read_text(encoding="utf-8")) if Path(a.trending).is_file() else None
    except (OSError, ValueError) as err:
        print(f"Stopped, nothing written: {err}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build(seen, entries, today, hot), encoding="utf-8")
    print(f"{len(entries)} kept entries across {len(seen.get('runs', []))} runs. Dashboard: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
