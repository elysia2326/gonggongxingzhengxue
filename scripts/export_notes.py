from __future__ import annotations

import html
import posixpath
import re
import subprocess
from pathlib import Path


DESKTOP = Path(r"C:/Users/23697/Desktop")
OUT_ROOT = Path(__file__).resolve().parents[1]
PANDOC = Path(r"C:/Users/23697/AppData/Local/Pandoc/pandoc.exe")


def find_source_root() -> Path:
    env_root = __import__("os").environ.get("PA_REVIEW_SRC")
    if env_root:
        candidate = Path(env_root)
        if candidate.exists():
            return candidate
    for candidate in DESKTOP.iterdir():
        if candidate.is_dir() and candidate.name == "公共行政学期末复习":
            inner = candidate / "复习"
            if inner.exists():
                return inner
    raise FileNotFoundError("Could not locate the public administration review source folder on Desktop.")


SRC_ROOT = find_source_root()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()


def build_note_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for md in SRC_ROOT.rglob("*.md"):
        rel = md.relative_to(SRC_ROOT)
        html_path = rel.with_suffix(".html").as_posix()
        stem = md.stem
        mapping[stem] = html_path
        mapping[normalize_name(stem)] = html_path
        mapping[normalize_name(stem).replace("_", "")] = html_path
    return mapping


NOTE_MAP = build_note_map()


def link_target(text: str) -> str | None:
    if text in NOTE_MAP:
        return NOTE_MAP[text]
    if text.startswith("第") and "章" in text:
        compact = text.replace(" ", "")
        if compact in NOTE_MAP:
            return NOTE_MAP[compact]
    return None


def replace_wikilinks(text: str, current_rel: Path) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1)
        target, _, alias = inner.partition("|")
        target = normalize_name(target)
        alias = alias or target
        href = link_target(target)
        if not href:
            return html.escape(alias)
        depth = 0 if current_rel.parent == Path(".") else len(current_rel.parent.parts)
        final_href = ("../" * depth) + Path(href).as_posix()
        return f'<a href="{html.escape(final_href)}">{html.escape(alias)}</a>'

    return re.sub(r"\[\[([^\]]+)\]\]", repl, text)


def md_to_html_fragment(md_path: Path) -> str:
    proc = subprocess.run(
        [
            str(PANDOC),
            "--from",
            "gfm",
            "--to",
            "html",
            "--wrap",
            "none",
        ],
        input=read_text(md_path),
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=True,
    )
    return proc.stdout


def extract_title(md_text: str, fallback: str) -> str:
    for line in md_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def wrap_page(title: str, body_html: str, nav_html: str, rel_prefix: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{rel_prefix}assets/style.css">
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="crumbs"><a href="{rel_prefix}index.html">首页</a> / {html.escape(title)}</div>
      <div class="crumbs">公共行政学期末复习</div>
    </div>
    <div class="page">
      {nav_html}
      <div class="note-body">
        {body_html}
      </div>
    </div>
  </div>
</body>
</html>
"""


def render_source(md_path: Path) -> tuple[str, str]:
    raw = read_text(md_path)
    title = extract_title(raw, md_path.stem)
    body_html = md_to_html_fragment(md_path)
    body_html = replace_wikilinks(body_html, md_path.relative_to(SRC_ROOT).with_suffix(".html"))
    return title, body_html


def nav_for(md_path: Path) -> str:
    rel = md_path.relative_to(SRC_ROOT)
    if rel.parts[0] == "01_章节复习":
        return '<p class="footer-note"><a href="index.html">返回章节目录</a></p>'
    if rel.parts[0] == "06_案例分析":
        return '<p class="footer-note"><a href="index.html">返回案例分析目录</a></p>'
    return f'<p class="footer-note"><a href="../index.html">返回首页</a></p>'


SKIP_INDEX_DIRS = {".github", "assets", "scripts"}


def humanize_path(path: Path) -> str:
    return " / ".join(part.replace("_", " ") for part in path.parts)


def generate_directory_index(dir_path: Path) -> None:
    rel = dir_path.relative_to(OUT_ROOT)
    depth = len(rel.parts)
    prefix = "../" * depth

    subdirs = [
        p for p in sorted(dir_path.iterdir(), key=lambda x: x.name)
        if p.is_dir() and not p.name.startswith(".") and p.name not in SKIP_INDEX_DIRS
    ]
    files = [
        p for p in sorted(dir_path.iterdir(), key=lambda x: x.name)
        if p.is_file() and p.suffix == ".html" and p.name != "index.html"
    ]

    subdir_cards = ""
    if subdirs:
        cards = []
        for subdir in subdirs:
            count = sum(1 for _ in subdir.rglob("*.html") if _.name != "index.html")
            cards.append(
                f'''<a class="card" href="{html.escape(subdir.name)}/index.html">
  <h3>{html.escape(subdir.name.replace("_", " "))}</h3>
  <p>{count} 个页面</p>
</a>'''
            )
        subdir_cards = "<h2 class=\"section-title\">子目录</h2><div class=\"grid\">" + "".join(cards) + "</div>"

    file_list = ""
    if files:
        items = []
        for file in files:
            label = file.stem.replace("_", " ")
            items.append(
                f'<a class="mini" href="{html.escape(file.name)}"><strong>{html.escape(label)}</strong><span>页面</span></a>'
            )
        file_list = "<h2 class=\"section-title\">页面</h2><div class=\"list\">" + "".join(items) + "</div>"

    if not subdir_cards and not file_list:
        file_list = '<p class="muted">这里暂时没有可展示的 HTML 页面。</p>'

    title = humanize_path(rel)
    body = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="{prefix}assets/style.css">
</head>
<body>
  <div class="wrap">
    <div class="topbar">
      <div class="crumbs"><a href="{prefix}index.html">首页</a> / {html.escape(title)}</div>
      <div class="crumbs">目录页</div>
    </div>
    <div class="page">
      <h1>{html.escape(title)}</h1>
      <p class="muted">本目录包含 {len(files)} 个页面{f'，以及 {len(subdirs)} 个子目录' if subdirs else ''}。</p>
      {subdir_cards}
      {file_list}
    </div>
  </div>
</body>
</html>
"""
    write_text(dir_path / "index.html", body)


def generate_indexes() -> None:
    for dir_path in sorted(
        [p for p in OUT_ROOT.rglob("*") if p.is_dir()],
        key=lambda p: len(p.parts),
    ):
        rel = dir_path.relative_to(OUT_ROOT)
        if rel.parts and rel.parts[0] in SKIP_INDEX_DIRS:
            continue
        if rel == Path("."):
            continue
        generate_directory_index(dir_path)


def main() -> None:
    for md in SRC_ROOT.rglob("*.md"):
        rel = md.relative_to(SRC_ROOT)
        out_html = OUT_ROOT / rel.with_suffix(".html")
        title, body_html = render_source(md)
        depth = 0 if rel.parent == Path(".") else len(rel.parts) - 1
        page = wrap_page(title, body_html, nav_for(md), rel_prefix="../" * depth)
        write_text(out_html, page)
    generate_indexes()


if __name__ == "__main__":
    main()
