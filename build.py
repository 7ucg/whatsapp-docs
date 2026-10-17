#!/usr/bin/env python3
"""Assemble .site-src (English sources + translations) and build the site."""
import hashlib, pathlib, re, shutil, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / ".site-src"
LANGS = ["de", "es", "pt-BR", "ru", "ar", "tr"]
STALE = {
    "de": "Diese Übersetzung ist möglicherweise veraltet. Maßgeblich ist das englische Original.",
    "es": "Esta traducción puede estar desactualizada. El original en inglés es la versión de referencia.",
    "pt-BR": "Esta tradução pode estar desatualizada. O original em inglês é a versão de referência.",
    "ru": "Этот перевод может быть устаревшим. Актуальна английская версия.",
    "ar": "قد تكون هذه الترجمة قديمة. النسخة الإنجليزية هي المرجع.",
    "tr": "Bu çeviri güncel olmayabilir. Geçerli sürüm İngilizce orijinaldir.",
}
HASH = re.compile(r"^<!--\s*src-sha1:\s*([0-9a-f]{40})\s*-->\s*\n")


def sha(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()


def main():
    shutil.rmtree(SRC, ignore_errors=True)
    shutil.rmtree(ROOT / "site", ignore_errors=True)
    shutil.copytree(ROOT / "site-extra", SRC)
    en = {p.name: p for p in list(ROOT.glob("WA_*.md")) + [ROOT / "CHANGELOG.md"]}
    for name, p in en.items():
        shutil.copy(p, SRC / name)
    # report standard: Version line gets a hard line break
    for p in SRC.glob("WA_*.md"):
        t = re.sub(r"(?m)^(\*\*Version:\*\*.*)$", r"\1  ", p.read_text())
        p.write_text(t)
    stale, missing = [], []
    for lang in LANGS:
        d = ROOT / "translations" / lang
        for name, p in list(en.items()) + [("index.md", ROOT / "site-extra" / "index.md")]:
            if name == "CHANGELOG.md":
                continue
            t = d / name
            if not t.exists():
                missing.append(f"{lang}/{name}")
                continue
            text = t.read_text()
            m = HASH.match(text)
            body = HASH.sub("", text, count=1)
            if m and m.group(1) != sha(p):
                stale.append(f"{lang}/{name}")
                body = f'!!! warning ""\n    {STALE[lang]}\n\n' + body
            if name.startswith("WA_"):
                body = re.sub(r"(?m)^(\*\*(?:Version|الإصدار|Versión|Versão|Версия|Sürüm):\*\*.*)$", r"\1  ", body)
            out = SRC / (name[:-3] + f".{lang}.md")
            out.write_text(body)
    cfg = (ROOT / "mkdocs.yml").read_text()
    h = hashlib.sha1(b"".join(p.read_bytes() for p in (ROOT / "site-extra").rglob("*") if p.is_file() and p.suffix in (".js", ".css"))).hexdigest()[:8]
    cfg = re.sub(r"(stylesheets/extra\.css|javascripts/extra\.js)", rf"\1?v={h}", cfg)
    tmp = ROOT / ".mkdocs.build.yml"
    tmp.write_text(cfg)
    try:
        r = subprocess.run([str(ROOT / ".venv/bin/mkdocs"), "build", "-q", "-f", str(tmp)], capture_output=True, text=True)
        if r.returncode:
            sys.exit(r.stdout + r.stderr)
    finally:
        tmp.unlink(missing_ok=True)
    sm = ROOT / "site" / "sitemap.xml"
    if sm.exists():
        for lang in LANGS:
            shutil.copy(sm, ROOT / "site" / lang / "sitemap.xml")
    print(f"built: {ROOT/'site'} (v={h}); stale={len(stale)} missing={len(missing)}")
    for s in stale: print("  stale:", s)
    if "-v" in sys.argv:
        for s in missing: print("  missing:", s)


main()
