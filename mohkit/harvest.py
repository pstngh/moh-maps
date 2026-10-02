"""Inputs for a history harvest (CLAUDE.md "The learning loop"): past sessions shrunk to what
holds lessons.

``condense`` turns a Claude Code transcript (``~/.claude/projects/<project>/*.jsonl``,
200-700 MB in all for this repo's first three days) into text a subagent can read whole: the
user's messages (typed and queued ones, in full), the agent's own words, every tool call
(Bash commands, edited paths with the old/new text clipped) and the first and last few
hundred characters of each tool result, with timestamps (UTC). Thinking blocks are stored
empty, attachments and sidechains are skipped. On 2026-10-02 the 11 transcripts (6-45 MB
each) came out at 170-730 KB.

``git_history`` writes the commit log of a branch (messages + changed files) and the
history of one file (``HANDOFF.md``: only the lines each commit changed, ``-`` removed,
``+`` added), since old HANDOFF versions held session notes later trimmed.

    python -m mohkit.harvest ~/.claude/projects/-Users-pstn-Documents-moh-maps/*.jsonl -o out/
    python -m mohkit.harvest --git . -o out/
"""

from __future__ import annotations

import argparse
import datetime
import difflib
import json
from pathlib import Path
from typing import Iterable, Union


def _clip(s: str, head: int, tail: int = 0) -> str:
    s = s.strip()
    if len(s) <= head + tail + 20:
        return s
    if tail:
        return s[:head] + f"\n  [...{len(s) - head - tail} chars...]\n  " + s[-tail:]
    return s[:head] + f" [...{len(s) - head} chars]"


def _result_text(c) -> str:
    if isinstance(c, str):
        return c
    out = []
    for x in c or []:
        if x.get("type") == "text":
            out.append(x["text"])
        elif x.get("type") == "image":
            out.append("[image]")
    return "\n".join(out)


def _tool_input(name: str, inp: dict) -> str:
    if name == "Bash":
        return inp.get("command", "") + (f"   # {inp['description']}" if inp.get("description") else "")
    if name == "Edit":
        return (f"{inp.get('file_path')}\n  OLD: {_clip(inp.get('old_string', ''), 300)}\n"
                f"  NEW: {_clip(inp.get('new_string', ''), 600)}")
    if name == "Write":
        return f"{inp.get('file_path')} ({len(inp.get('content', ''))} chars)\n  {_clip(inp.get('content', ''), 600)}"
    if name == "Read":
        return f"{inp.get('file_path')} {inp.get('offset', '')} {inp.get('limit', '')}"
    if name in ("Agent", "Task"):
        return f"{inp.get('description')}: {_clip(inp.get('prompt', ''), 1200)}"
    return json.dumps(inp)[:600]


def condense_lines(lines: Iterable[str]) -> Iterable[str]:
    """Condensed transcript lines (see the module docstring). Text that arrives with a tool
    result (an image the agent read) is shown as tool output, not as a user message."""
    seen: set[str] = set()

    def user(ts: str, text: str, tag: str = "USER") -> Iterable[str]:
        key = text.strip()[:200]
        if key not in seen:
            seen.add(key)
            yield f"\n[{ts}] {tag}: {_clip(text, 8000)}\n\n"

    for line in lines:
        try:
            d = json.loads(line)
        except ValueError:
            continue
        if d.get("isSidechain"):
            continue
        t = d.get("type")
        ts = (d.get("timestamp") or "")[5:16].replace("T", " ")
        if t == "attachment":
            a = d.get("attachment") or {}
            if a.get("type") == "queued_command":
                p = a.get("prompt")
                p = _result_text(p) if isinstance(p, list) else (p or "")
                if p.lstrip().startswith("<task-notification>"):
                    i = p.find("<summary>")
                    yield f"[{ts}] NOTIFY: {_clip(p[i:i + 300] if i >= 0 else p, 300)}\n"
                else:
                    yield from user(ts, p, "USER(queued)")
            elif a.get("type") == "hook_blocking_error":
                yield f"[{ts}] HOOK-BLOCK: {_clip(json.dumps(a.get('blockingError')), 300)}\n"
            continue
        m = d.get("message")
        if not isinstance(m, dict):
            continue
        c = m.get("content")
        if t == "user":
            if d.get("isMeta"):   # harness-made, e.g. the size note of an image the agent read
                yield f"[{ts}] META: {_clip(_result_text(c), 300)}\n"
                continue
            if isinstance(c, str):
                yield from user(ts, c)
                continue
            from_tool = any(x.get("type") == "tool_result" for x in c or [])
            for x in c or []:
                if x.get("type") == "text":
                    if from_tool:      # e.g. "[Image: original 1920x2660 ...]" of a Read
                        yield f"  -> {_clip(x['text'], 350)}\n"
                    else:
                        yield from user(ts, x["text"])
                elif x.get("type") == "image":
                    yield f"[{ts}] USER: [image]\n"
                elif x.get("type") == "tool_result":
                    r = _result_text(x.get("content"))
                    yield f"  ERROR: {_clip(r, 700, 300)}\n" if x.get("is_error") else f"  -> {_clip(r, 350, 250)}\n"
        elif t == "assistant":
            for x in c or []:
                if x.get("type") == "text" and x["text"].strip():
                    yield f"[{ts}] A: {x['text'].strip()}\n"
                elif x.get("type") == "tool_use":
                    yield f"[{ts}] TOOL {x['name']}: {_tool_input(x['name'], x.get('input', {}))}\n"


def condense(src: Union[str, Path], dst: Union[str, Path]) -> int:
    """Write the condensed transcript of ``src`` to ``dst``; returns its size in bytes."""
    with open(src, encoding="utf-8", errors="replace") as f, open(dst, "w", encoding="utf-8") as out:
        for piece in condense_lines(f):
            out.write(piece)
    return Path(dst).stat().st_size


def git_history(repo: Union[str, Path], out_dir: Union[str, Path], branch: str = "main",
                path: str = "HANDOFF.md") -> tuple[int, int]:
    """``commits.txt`` (oldest first: id, local time, message, changed files) and
    ``<path stem>_diffs.txt`` (the lines each commit changed in ``path``) under ``out_dir``.
    Returns (commits, versions of ``path``). Uses dulwich (system git may be blocked)."""
    from dulwich.repo import Repo
    r = Repo(str(repo))
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    prev, n, nv = None, 0, 0
    with open(out / "commits.txt", "w") as log, open(out / f"{Path(path).stem.lower()}_diffs.txt", "w") as hd:
        for e in r.get_walker(include=[r.refs[f"refs/heads/{branch}".encode()]], reverse=True):
            c = e.commit
            n += 1
            t = datetime.datetime.fromtimestamp(c.commit_time, datetime.timezone(datetime.timedelta(seconds=c.commit_timezone)))
            files = []
            for ch in e.changes():
                ch = ch[0] if isinstance(ch, list) else ch
                files.append((ch.new.path or ch.old.path).decode())
            msg = c.message.decode("utf-8", "replace").strip()
            log.write(f"=== {c.id[:7].decode()} {t:%m-%d %H:%M}\n{msg}\n  files: {', '.join(files[:25])}"
                      f"{' ...' if len(files) > 25 else ''}\n\n")
            try:
                _, sha = r.object_store[c.tree].lookup_path(r.object_store.__getitem__, path.encode())
                text = r.object_store[sha].data.decode("utf-8", "replace")
            except KeyError:
                text = None
            if text != prev:
                nv += 1
                diff = [ln for ln in difflib.unified_diff((prev or "").splitlines(), (text or "").splitlines(),
                                                          lineterm="", n=0)
                        if ln.startswith(("+", "-")) and not ln.startswith(("+++", "---"))]
                hd.write(f"=== {c.id[:7].decode()} {t:%m-%d %H:%M} {msg.splitlines()[0] if msg else ''}\n"
                         + "\n".join(diff) + "\n\n")
                prev = text
    return n, nv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m mohkit.harvest", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("transcripts", nargs="*", help="Claude Code .jsonl transcripts")
    ap.add_argument("--git", help="also write the commit log and HANDOFF.md history of this repo")
    ap.add_argument("-o", "--out", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for t in a.transcripts:
        size = condense(t, out / (Path(t).stem + ".txt"))
        print(f"{Path(t).name}: {Path(t).stat().st_size / 1e6:.1f} MB -> {size / 1e3:.0f} KB")
    if a.git:
        n, nv = git_history(a.git, out)
        print(f"{n} commits, {nv} versions of HANDOFF.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
