#!/usr/bin/env python3
"""Structural check: translated file vs English source (headings, code fences, table rows, code content)."""
import hashlib, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent


def stats(t):
    lines = t.splitlines()
    fences = sum(1 for l in lines if l.lstrip().startswith("```"))
    heads = [re.match(r"#+", l).group(0) + (re.match(r"#+\s*(\d+(?:\.\d+)*\.?)", l) or [None, ""])[1] for l in lines if re.match(r"#{1,6}\s", l)]
    rows = sum(1 for l in lines if l.lstrip().startswith("|"))
    code = re.findall(r"```.*?\n(.*?)```", t, re.S)
    return fences, heads, rows, code


def main(lang, names):
    ok = True
    for n in names:
        src, tr = ROOT / n, ROOT / "translations" / lang / n
        if n == "index.md":
            src = ROOT / "site-extra" / "index.md"
        if not tr.exists():
            print(f"MISSING {lang}/{n}"); ok = False; continue
        s, t = src.read_text(), tr.read_text()
        m = re.match(r"<!--\s*src-sha1:\s*([0-9a-f]{40})\s*-->", t)
        problems = []
        if not m or m.group(1) != hashlib.sha1(src.read_bytes()).hexdigest():
            problems.append("src-sha1 header missing or wrong")
        a, b = stats(s), stats(re.sub(r"^<!--.*?-->\s*", "", t, count=1))
        if a[0] != b[0]: problems.append(f"code fences {a[0]} vs {b[0]}")
        if a[1] != b[1]: problems.append(f"headings differ ({len(a[1])} vs {len(b[1])})")
        if a[2] != b[2]: problems.append(f"table rows {a[2]} vs {b[2]}")
        if len(a[3]) == len(b[3]):
            diff = sum(1 for x, y in zip(a[3], b[3]) if x.strip() != y.strip())
            if diff: problems.append(f"{diff} code blocks changed")
        print(("OK      " if not problems else "PROBLEM ") + f"{lang}/{n}" + ("" if not problems else ": " + "; ".join(problems)))
        ok &= not problems
    return ok


if __name__ == "__main__":
    lang = sys.argv[1]
    names = sys.argv[2:] or [p.name for p in ROOT.glob("WA_*.md")] + ["index.md"]
    sys.exit(0 if main(lang, names) else 1)
