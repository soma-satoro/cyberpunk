"""Replace common Unicode punctuation with ASCII in text source files."""
import pathlib

REPL = {
    "\u2019": "'",
    "\u2018": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2014": "--",
    "\u2013": "-",
    "\u2026": "...",
    "\u2192": "->",
    "\u2194": "<->",
    "\u00a0": " ",
    "\u00d7": "x",  # multiplication sign
    "\u2212": "-",  # minus sign
    "\u00f7": "/",  # division sign
    "\u00ae": "(R)",  # registered
    "\u26a0": "[!]",  # warning sign
    "\ufe0f": "",  # variation selector (emoji style)
}


def normalize_text(s: str) -> str:
    for k, v in REPL.items():
        s = s.replace(k, v)
    return s


SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}
SKIP_EXT = {".pyc", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".db", ".sqlite3", ".ico"}


def main():
    root = pathlib.Path(".")
    changed = 0
    leftover = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_EXT:
            continue
        if p.suffix.lower() not in (".py", ".txt", ".wiki", ".md"):
            continue
        try:
            raw = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        new = normalize_text(raw)
        if new != raw:
            p.write_text(new, encoding="utf-8", newline="\n")
            print("updated", p)
            changed += 1
        if any(ord(c) > 127 for c in new):
            leftover.append(p)
    print("files changed:", changed)
    if leftover:
        print("still have non-ASCII after punctuation map:")
        for p in leftover:
            t = p.read_text(encoding="utf-8")
            ch = sorted({c for c in t if ord(c) > 127})
            print(" ", p, [hex(ord(x)) for x in ch[:12]])


if __name__ == "__main__":
    main()
