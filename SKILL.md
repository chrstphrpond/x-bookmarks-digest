---
name: x-bookmarks-digest
description: Turn the user's X (Twitter) bookmarks and likes into a backlog of Claude skills, MCP servers, repos and techniques in the Obsidian vault. Use when asked to check, harvest or go through X saves, bookmarks or likes, "what did I save on X for Claude", "x-saves", or for the weekly X saves run. Read-only on X.
---

# X saves harvest

Collects posts from X through an Orca tab, keeps the new AI-tool ones, expands them with full text and repo facts, and appends what is worth keeping to `Notes/X Saves for Claude.md` in the notes vault. Remembers handled posts, so each run shows only new saves.

`S` below is this skill's folder; `RUN` is `~/.local/state/x-bookmarks-digest/runs/<YYYY-MM-DD>`.

## 1. Preflight

- `orca status` shows `runtimeReachable: true`. If not, ask the user to open Orca.
- Use `--worktree path:<this session's working directory>` written out literally. The `orca-worktree-guard` hook rejects variables and other worktrees.
- `python3 S/scripts/xsaves.py status` shows how many posts are handled and the last runs.
- `mkdir -p RUN`.

## 2. Collect

Each command opens its own Orca tab, scrolls in small steps, saves the posts and closes the tab:

```
python3 S/scripts/xsaves.py collect --source bookmarks --worktree path:/abs/worktree --expect-account <your handle> --out RUN/bookmarks.json
python3 S/scripts/xsaves.py collect --source likes --worktree path:/abs/worktree --expect-account <your handle> --out RUN/likes.json
```

- It stops at the end of the list, or after 15 handled posts in a row. A first run on a long likes list takes 15–20 minutes, so run it in the background.
- The feed is optional sampling: `--source feed --max-steps 60`.
- A topic the user asks for: `--source search --query "claude blender" --max-steps 40 --stop-after-known 0 --out RUN/search-<topic>.json` (X's Top tab). Search posts are not saves, so put them in their own `### From search: <query>` group at the end of the run section.
- If the user opens something else in the collector's tab, the script stops with "tab moved to …" and keeps what it had. Rerun that source.
- Wrong account: the script stops. Ask the user to switch accounts in the Orca tab, then rerun.
- Few posts and "end of list" too early means X stopped loading because the tab is not drawn. Rerun with `--focus`, which brings the tab forward in Orca, and tell the user why.

## 3. Expand

```
python3 S/scripts/xsaves.py expand RUN/bookmarks.json RUN/likes.json --out RUN/digest.json --md RUN/digest.md
```

It drops handled posts, keeps the AI-related ones by keyword, fetches full text, X articles and quoted posts from the public fxtwitter API, and checks every linked GitHub repo with `gh` (stars, last push, `SKILL.md` folders inside). If it reports 0 new posts, say so and stop.

## 4. Judge

Read all of `RUN/digest.md` (in chunks if long). Give each post one kind:

| Kind | Keep when |
|---|---|
| Skill | the repo contains `SKILL.md` folders, or the post gives a `skills add` command |
| MCP server | it adds tools to Claude through MCP |
| Repo or tool | open-source project or app that works with Claude |
| Technique | a reusable prompt, workflow or method, with enough detail in the post to use |
| Resource | free API, asset or footage library, prompt gallery, inspiration site |
| Build idea | something worth building as our own skill |
| Drop | hype with nothing usable; "comment to get it" with no method in the post; off-topic; or unsafe (cracking paid software, impersonating real people, spam) |

- Merge posts about the same repo or tool into one entry and link the most useful post.
- "same name as an installed skill" is only a name match. Confirm with `orca skills installed` before writing "Installed".
- Note overlaps with installed skills, for example HyperFrames, media-use or impeccable.

## 5. Write the vault note

File: `~/notes/X Saves for Claude.md` (set this to your own notes folder). Create it from the template below if missing. Otherwise insert the new run section directly under the intro, newest first, with a targeted edit. Never rewrite earlier runs.

```
# X Saves for Claude

#reference #x-saves #claude-code

Claude skills, MCP servers, repos and techniques from my X bookmarks and likes, newest run first. Written by the `x-bookmarks-digest` skill; handled post ids are in `~/.local/state/x-bookmarks-digest/seen.json`.

## 2026-10-25

41 new saves checked, 23 kept.

### Skills

- [emilkowalski/skills](https://github.com/emilkowalski/skills): animation review, vocabulary and design-engineering skills. 49k stars, pushed 2026-10-11. [post](https://x.com/emilkowalski/status/2077404975555031509)
```

- Groups in this order, empty ones left out: Skills, MCP servers, Repos and tools, Techniques, Resources, Build ideas.
- One line per entry: link, what it does in 20 words or fewer, facts (stars and last push for repos), then `[post](url)`. Add "Installed." or "Overlaps <skill>." when true. For techniques, quote the key instruction in under 40 words.
- Vault rules: no emojis, no editorializing, and no `- [ ]` task lines, so the task list stays clean.

## 6. Mark handled and report

Only after the note is saved:

```
python3 S/scripts/xsaves.py mark-seen RUN/digest.json --note "kept 23"
```

Then report in chat: posts collected, new, AI-related, kept and dropped; the three to five best new finds, one line each; and the note path.

## 7. Dashboard (optional)

One page showing every run, what was kept by kind, and the newest finds. It reads only the ledger and the note:

```
python3 S/scripts/dashboard.py --note "~/notes/X Saves for Claude.md" --out RUN/dashboard.html
```

Give the user the path. If they ask to see it, open it in a browser tab.

## Rules

- Read-only on X: never like, bookmark, follow, reply or post, and never sign in for the user.
- Only public post ids go to fxtwitter; repo names go to the GitHub API. Nothing else leaves the machine.
- Suggest installs; do not install anything found here without the user's go-ahead.
