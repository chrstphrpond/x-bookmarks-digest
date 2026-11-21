#!/usr/bin/env python3
"""Harvest X bookmarks and likes for Claude: collect through Orca, expand, track handled posts.

Subcommands:
  collect    scroll one X list in its own Orca tab and save the posts it shows
  expand     keep new AI-tool posts, fetch full text (fxtwitter) and repo facts (gh)
  mark-seen  record every post in a digest as handled
  status     show how many posts are handled and the last runs

Read-only on X: it never posts, likes, bookmarks or follows.
"""
import argparse
import json
import re
import subprocess
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

STATE_DIR = Path.home() / ".local/state/x-saves-harvest"
SEEN_FILE = STATE_DIR / "seen.json"
SOURCES = {
    "bookmarks": "https://x.com/i/history",
    "likes": "https://x.com/i/history/likes",
    "feed": "https://x.com/home",
    "search": "https://x.com/search?q={query}&src=typed_query&f=top",
}

# Collects the posts currently rendered. X recycles rows as you scroll, so this runs after every step.
COLLECT_JS = r"""(() => {
  const s = window.__xs = window.__xs || {items: {}};
  const fresh = [];
  for (const a of document.querySelectorAll('article[data-testid=tweet]')) {
    const href = [...a.querySelectorAll('a[href*="/status/"]')].map(x => x.getAttribute('href'))
      .find(h => /^\/[^/]+\/status\/\d+$/.test(h));
    if (!href || s.items[href]) continue;
    const text = [...a.querySelectorAll('[data-testid=tweetText]')].map(t => t.innerText).join('\n[quoted]\n');
    const user = ((a.querySelector('[data-testid=User-Name]') || {}).innerText || '').replace(/\n/g, ' ');
    const card = ((a.querySelector('[data-testid="card.wrapper"]') || {}).innerText || '').slice(0, 300);
    const time = (a.querySelector('time') || {}).dateTime || '';
    s.items[href] = {link: href, user, time, text, card};
    fresh.push(href);
  }
  const prof = document.querySelector('[data-testid=AppTabBar_Profile_Link]');
  return JSON.stringify({fresh, y: Math.round(scrollY), h: document.body.scrollHeight,
    me: prof ? prof.getAttribute('href') : '', url: location.href});
})()"""

AI_RE = re.compile(
    r"claude|anthropic|opus|sonnet|haiku|fable|skills?\b|mcp|agent|prompt|codex|cursor|github|open.?source|repo\b"
    r"|hyperframes|remotion|gsap|\bai\b|\bllm|gpt|chatgpt|gemini|grok|nano banana|seedance|kling|higgsfield|vibe.?cod"
    r"|n8n|automat|workflow|api\b|npx |pnpm |pip install",
    re.I,
)
REPO_RES = [
    re.compile(r"github\.com/([\w.-]+)/([\w.-]+)", re.I),
    re.compile(r"skills\.sh/([\w.-]+)/([\w.-]+)", re.I),
    re.compile(r"skills add ([\w.-]+)/([\w.-]+)", re.I),
    re.compile(r"GitHub - ([\w.-]+)/([\w.-]+):"),  # link-card title
]
NOT_OWNERS = {"orgs", "features", "sponsors", "topics", "marketplace", "settings", "apps", "login", "about"}
INSTALL_RE = re.compile(r"(?:npx|pnpm dlx|bunx) skills add [\w./@-]+|claude mcp add [^\n]+|/plugin install [^\s]+", re.I)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def status_id(link):
    m = re.search(r"/status/(\d+)", link)
    return m.group(1) if m else link


def load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {"ids": {}, "runs": []}


def save_seen(seen):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SEEN_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(seen, indent=1))
    tmp.replace(SEEN_FILE)


# ---------- collect ----------

def orca(args, worktree, page=None, timeout=60):
    cmd = ["orca", *args, "--worktree", worktree, "--json"]
    if page:
        cmd += ["--page", page]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError(f"orca {' '.join(args[:2])} failed: {(r.stderr or r.stdout).strip()[:300]}")
    out = json.loads(r.stdout)
    if not out.get("ok"):
        raise RuntimeError(f"orca {' '.join(args[:2])} failed: {json.dumps(out)[:300]}")
    return out["result"]


def page_eval(js, worktree, page):
    return json.loads(orca(["eval", "--expression", js], worktree, page)["result"])


def collect(a):
    if a.source == "search" and not a.query:
        raise SystemExit("--source search needs --query")
    url = SOURCES[a.source].format(query=urllib.parse.quote(a.query or ""))
    known = set(load_seen()["ids"])
    created = orca(["tab", "create", "--url", url], a.worktree)
    page = created.get("browserPageId") or created.get("pageId") or created.get("tab", {}).get("browserPageId")
    if not page:
        tabs = orca(["tab", "list"], a.worktree)["tabs"]
        page = next(t["browserPageId"] for t in tabs if t["active"])
    log(f"{a.source}: opened tab {page}")
    try:
        if a.focus:
            orca(["tab", "switch", "--focus"], a.worktree, page)
        time.sleep(6)
        order, stall, stop, account = [], 0, "max steps", ""
        for step in range(a.max_steps):
            orca(["screenshot", "--format", "jpeg"], a.worktree, page)  # forces a frame so X keeps loading
            res = page_eval(COLLECT_JS, a.worktree, page)
            if step == 0:
                if any(k in res["url"] for k in ("/login", "/i/flow", "/onboarding", "mode=login")) or not res["me"].strip("/"):
                    raise SystemExit("Not signed in to X in this Orca tab. Sign in, then run again.")
                account = res["me"].strip("/")
                log(f"{a.source}: signed in as @{account}")
                if a.expect_account and account.lower() != a.expect_account.lstrip("@").lower():
                    raise SystemExit(f"Signed in as @{account}, expected @{a.expect_account.lstrip('@')}. Stopping.")
                start_url = res["url"]
            elif res["url"] != start_url:  # someone used the tab for something else
                stop = f"tab moved to {res['url']}"
                break
            order += res["fresh"]
            stall = 0 if res["fresh"] else stall + 1
            tail = order[-a.stop_after_known:]
            if a.stop_after_known and len(tail) == a.stop_after_known and all(status_id(h) in known for h in tail):
                stop = "reached posts already handled"
                break
            if a.source != "feed" and stall >= a.max_stall:
                stop = "end of list"
                break
            if step % 20 == 0:
                log(f"{a.source}: step {step}, {len(order)} posts")
            if stall and stall % 4 == 3:
                orca(["scroll", "--direction", "up", "--amount", "400"], a.worktree, page)
                time.sleep(1)
            orca(["scroll", "--direction", "down", "--amount", str(a.step_px)], a.worktree, page)
            time.sleep(1.0 + (2.0 if stall else 0))
        items = json.loads(orca(["eval", "--expression", "JSON.stringify(window.__xs.items)"], a.worktree, page)["result"])
    finally:
        if not a.keep_tab:
            try:
                orca(["tab", "close"], a.worktree, page)
            except Exception as e:  # leaving a tab open is harmless
                log(f"could not close tab: {e}")
    rows = [dict(items[h], id=status_id(h), sources=[a.source]) for h in order if h in items]
    out = {"source": a.source, "account": account, "collected_at": datetime.now().isoformat(timespec="seconds"),
           "stopped": stop, "items": rows}
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    new = sum(1 for r in rows if r["id"] not in known)
    print(f"{a.source}: {len(rows)} posts ({new} not handled yet), stopped: {stop} -> {a.out}")


# ---------- expand ----------

def run_json(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def url_facets(raw):
    return [f.get("replacement") or f.get("original") for f in (raw or {}).get("facets", []) if f.get("type") == "url"]


def fetch_post(pid):
    d = run_json(["curl", "-s", "--max-time", "20", f"https://api.fxtwitter.com/i/status/{pid}"], timeout=30)
    t = (d or {}).get("tweet")
    if not t:
        return None
    art = t.get("article") or {}
    blocks = (art.get("content") or {}).get("blocks") or []
    q = t.get("quote") or {}
    return {
        "text": t.get("text", ""),
        "links": url_facets(t.get("raw_text")),
        "likes": t.get("likes"),
        "views": t.get("views"),
        "article_title": art.get("title"),
        "article": "\n".join(b.get("text", "") for b in blocks)[:6000],
        "quote": {"url": q.get("url"), "author": (q.get("author") or {}).get("screen_name"),
                  "text": q.get("text", "")[:2000], "links": url_facets(q.get("raw_text"))} if q else None,
    }


def find_repos(blob):
    repos = []
    for rx in REPO_RES:
        for owner, name in rx.findall(blob):
            name = re.sub(r"(\.git|[.…]+)$", "", name)
            if owner.lower() in NOT_OWNERS or not name:
                continue
            full = f"{owner}/{name}"
            if full.lower() not in {r.lower() for r in repos}:
                repos.append(full)
    return repos


def repo_facts(full):
    d = run_json(["gh", "api", f"repos/{full}"])
    if not d or "full_name" not in d:
        return {"repo": full, "found": False}
    tree = run_json(["gh", "api", f"repos/{d['full_name']}/git/trees/HEAD?recursive=1"], timeout=60) or {}
    # a SKILL.md at the repo root is one skill named after the repo
    skills = sorted({Path(e["path"]).parent.name or d["name"] for e in tree.get("tree", []) if e["path"].endswith("SKILL.md")})
    return {"repo": d["full_name"], "found": True, "stars": d.get("stargazers_count"),
            "pushed": (d.get("pushed_at") or "")[:10], "description": d.get("description"),
            "archived": d.get("archived"), "license": (d.get("license") or {}).get("spdx_id"), "skills": skills}


def installed_skill_names():
    names = set()
    # skill folders are often symlinks, which glob("**") does not follow, so walk two levels by hand
    for root in [Path.home() / ".claude/skills", Path.home() / ".agents/skills"]:
        for d in [*root.glob("*"), *root.glob("*/*")] if root.exists() else []:
            if (d / "SKILL.md").exists():
                names.add(d.name.lower())
    cache = Path.home() / ".claude/plugins/cache"
    names |= {f.parent.name.lower() for f in cache.glob("**/SKILL.md")} if cache.exists() else set()
    return names


def expand(a):
    seen = load_seen()["ids"]
    posts = {}
    for f in a.inputs:
        for r in json.loads(Path(f).read_text())["items"]:
            if r["id"] in posts:
                posts[r["id"]]["sources"] = sorted(set(posts[r["id"]]["sources"]) | set(r["sources"]))
            else:
                posts[r["id"]] = r
    new = [p for p in posts.values() if a.all or p["id"] not in seen]
    # posts that are only an article card or media show little text in the page, so fetch those and test the full text
    cand = [p for p in new if AI_RE.search(p["text"] + " " + p["card"]) or len(p["text"].strip()) < 20]
    log(f"{len(posts)} posts collected, {len(new)} not handled yet, {len(cand)} to fetch")
    with ThreadPoolExecutor(4) as pool:
        full = dict(zip([p["id"] for p in cand], pool.map(fetch_post, [p["id"] for p in cand])))
    failed = sum(1 for v in full.values() if not v)
    if failed:
        log(f"fxtwitter gave nothing for {failed} posts; their page text is used instead (rerun expand to retry)")

    def on_topic(p):
        f = full.get(p["id"]) or {}
        q = f.get("quote") or {}
        return AI_RE.search(" ".join([p["text"], p["card"], f.get("text", ""), f.get("article_title") or "", q.get("text", "")]))
    ai = [p for p in cand if on_topic(p)]
    ai_ids = {p["id"] for p in ai}
    skipped = [p["id"] for p in new if p["id"] not in ai_ids]
    repos = {}
    for p in ai:
        f = full.get(p["id"]) or {}
        q = f.get("quote") or {}
        # X wraps long URLs in the page text, so read links from the full text whenever fxtwitter answered
        parts = [f.get("text", ""), f.get("article", ""), q.get("text", ""), *f.get("links", []), *q.get("links", [])] if f else [p["text"]]
        blob = "\n".join([p["card"], *parts])
        p["full"] = f or None
        p["repos"] = find_repos(blob)
        p["install_cmds"] = sorted(set(INSTALL_RE.findall(blob)))
        for r in p["repos"]:
            repos[r.lower()] = r
    log(f"checking {len(repos)} repos with gh")
    with ThreadPoolExecutor(4) as pool:
        facts = {r.lower(): fct for r, fct in zip(repos.values(), pool.map(repo_facts, repos.values()))}
    have = installed_skill_names()
    for p in ai:
        found = {}  # renamed repos redirect, so two links can land on the same repo
        for r in p["repos"]:
            fct = facts[r.lower()]
            found.setdefault(fct["repo"].lower(), dict(fct, name_match=[s for s in fct.get("skills", []) if s.lower() in have]))
        p["repos"] = list(found.values())

    digest = {"generated": datetime.now().isoformat(timespec="seconds"), "collected": len(posts), "new": len(new),
              "ai": len(ai), "skipped_ids": skipped, "items": ai}
    Path(a.out).write_text(json.dumps(digest, ensure_ascii=False, indent=1))
    if a.md:
        Path(a.md).write_text(render_md(digest))
    print(f"{len(new)} new posts, {len(ai)} AI-related, {len(repos)} repos -> {a.out}" + (f" and {a.md}" if a.md else ""))


def render_md(d):
    out = [f"# X saves digest {d['generated'][:10]}", "",
           f"{d['collected']} collected, {d['new']} new, {d['ai']} AI-related, {len(d['skipped_ids'])} skipped as off-topic.", ""]
    for p in d["items"]:
        f = p.get("full") or {}
        handle = p["link"].split("/")[1]
        out.append(f"## @{handle} · {p['time'][:10]} · {', '.join(p['sources'])} · https://x.com{p['link']}")
        if f.get("likes") is not None:
            out.append(f"likes {f['likes']}, views {f.get('views')}")
        out.append((f.get("text") or p["text"])[:1500])
        if f.get("article_title"):
            out.append(f"ARTICLE: {f['article_title']} | {f['article'][:900]}".replace("\n", " / "))
        q = f.get("quote")
        if q and q.get("text"):
            out.append(f"QUOTE @{q['author']}: {q['text'][:600]}".replace("\n", " / "))
        links = [l for l in f.get("links", []) + ((q or {}).get("links") or []) if l]
        if links:
            out.append("LINKS: " + " ".join(dict.fromkeys(links)))
        for r in p["repos"]:
            if not r.get("found"):
                out.append(f"REPO {r['repo']}: not found")
                continue
            line = f"REPO {r['repo']}: {r['stars']} stars, pushed {r['pushed']}, {r['description'] or 'no description'}"
            if r["skills"]:
                line += f"; skills: {', '.join(r['skills'][:15])}"
            if r["name_match"]:
                line += f"; same name as an installed skill (check): {', '.join(r['name_match'])}"
            out.append(line)
        if p["install_cmds"]:
            out.append("INSTALL: " + " | ".join(p["install_cmds"]))
        out.append("")
    return "\n".join(out)


# ---------- state ----------

def mark_seen(a):
    d = json.loads(Path(a.digest).read_text())
    seen = load_seen()
    today = datetime.now().strftime("%Y-%m-%d")
    ids = [p["id"] for p in d["items"]] + d["skipped_ids"]
    for i in ids:
        seen["ids"].setdefault(i, today)
    seen["runs"].append({"date": today, "new": d["new"], "ai": d["ai"], "note": a.note})
    save_seen(seen)
    print(f"marked {len(ids)} posts as handled ({len(seen['ids'])} total)")


def status(_):
    seen = load_seen()
    print(f"{len(seen['ids'])} posts handled; state in {SEEN_FILE}")
    for r in seen["runs"][-5:]:
        print(f"  {r['date']}: {r['new']} new, {r['ai']} AI-related" + (f" ({r['note']})" if r.get("note") else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("collect")
    c.add_argument("--source", choices=SOURCES, required=True)
    c.add_argument("--worktree", required=True, help="literal Orca selector, e.g. path:/abs/session/worktree")
    c.add_argument("--query", help="search words for --source search")
    c.add_argument("--out", required=True)
    c.add_argument("--expect-account", help="stop unless signed in as this handle")
    c.add_argument("--max-steps", type=int, default=600)
    c.add_argument("--max-stall", type=int, default=10, help="steps without new posts before calling it the end")
    c.add_argument("--stop-after-known", type=int, default=15, help="stop after this many handled posts in a row; 0 = never")
    c.add_argument("--step-px", type=int, default=700)
    c.add_argument("--focus", action="store_true", help="bring the tab forward in Orca if X stops loading")
    c.add_argument("--keep-tab", action="store_true")
    c.set_defaults(fn=collect)
    e = sub.add_parser("expand")
    e.add_argument("inputs", nargs="+")
    e.add_argument("--out", required=True)
    e.add_argument("--md", help="also write a compact Markdown digest for reading")
    e.add_argument("--all", action="store_true", help="include posts already handled")
    e.set_defaults(fn=expand)
    m = sub.add_parser("mark-seen")
    m.add_argument("digest")
    m.add_argument("--note", default="")
    m.set_defaults(fn=mark_seen)
    s = sub.add_parser("status")
    s.set_defaults(fn=status)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
