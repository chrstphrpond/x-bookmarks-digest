# x-saves-harvest

A Claude Code skill I run once a week. It goes through my X bookmarks and likes, keeps the new posts about AI tools, checks each linked GitHub repo, and adds what is worth keeping to a note. It only reads; it never likes, follows, replies or posts.

Built with Claude Code by Christopher Pond Maquidato, October 2026.

## What it does

1. **Collect.** Opens my bookmarks and likes in a browser tab I am already signed in to, scrolls in small steps and saves the posts. It stops at the end of the list or after 15 posts in a row it has already handled.
2. **Expand.** Drops handled posts, keeps the AI-related ones, fetches the full text, and checks every linked GitHub repo with `gh` (stars, last push, whether it holds skills).
3. **Judge.** Claude sorts each post into a kind (skill, MCP server, repo, technique, resource, build idea) or drops it.
4. **Write.** Adds one dated section to the note, newest first. Earlier runs are never rewritten.
5. **Mark handled.** Only after the note is saved, so a failed run loses nothing.

## What keeps it reliable

- **It checks the account first.** `--expect-account` stops the run if the browser is signed in to a different account.
- **It remembers what it handled.** Post ids are kept in `~/.local/state/x-saves-harvest/seen.json`, so each run shows only new saves and a rerun never doubles an entry.
- **It stops loudly.** If the tab is moved, or the list stops loading early, the script says so and keeps what it had.
- **It never signs in for me.** If the session has expired it asks me to sign in.

## What's here

| File | What it is |
|---|---|
| `SKILL.md` | What Claude reads: the steps, the sorting rules, the note format |
| `scripts/xsaves.py` | Collecting, expanding and the handled-posts ledger. Plain Python, no packages |

## Needs

- Claude Code, with this folder copied to `~/.claude/skills/x-saves-harvest/`.
- The Orca app, whose `orca` CLI drives the browser tab the collector reads, and the `gh` CLI for repo facts.
- Your own X handle for `--expect-account`, and your own notes path in step 5 of `SKILL.md`.
