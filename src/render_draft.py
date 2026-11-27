"""블로그 초안(.md)을 네이버 블로그에 붙여 넣기 좋은 HTML로 바꾼다.

네이버 스마트에디터는 마크다운을 읽지 못한다. 대신 브라우저에서 렌더링된 글을
복사해 붙여 넣으면 제목, 굵은 글씨, 목록 같은 서식이 대부분 유지된다.
그래서 서식을 태그에 직접(inline style) 넣은 HTML 파일을 만든다.

사용법
  python src/render_draft.py drafts/<파일>.md
  -> drafts/<파일>.html 이 만들어지고 브라우저로 열린다. (--no-open 으로 열기 생략)
  브라우저에서 전체 선택(Cmd+A) -> 복사(Cmd+C) -> 네이버 글쓰기 화면에 붙여넣기(Cmd+V)
"""
import re
import subprocess
import sys
from pathlib import Path

import markdown

STYLES = {
    "h1": "font-size:26px;font-weight:bold;margin:0 0 24px;",
    "h2": "font-size:20px;font-weight:bold;margin:32px 0 12px;",
    "h3": "font-size:17px;font-weight:bold;margin:24px 0 8px;",
    "p": "font-size:15px;line-height:1.8;margin:0 0 14px;",
    "ul": "font-size:15px;line-height:1.8;margin:0 0 14px;padding-left:22px;",
    "ol": "font-size:15px;line-height:1.8;margin:0 0 14px;padding-left:22px;",
    "li": "margin:0 0 4px;",
    "blockquote": "border-left:4px solid #ccc;margin:0 0 14px;padding:4px 14px;color:#555;",
    "pre": (
        "background:#f5f5f5;border:1px solid #ddd;border-radius:4px;padding:12px;"
        "margin:0 0 16px;font-family:Menlo,Consolas,monospace;font-size:13px;"
        "line-height:1.6;white-space:pre-wrap;overflow-x:auto;"
    ),
}
INLINE_CODE = "background:#f0f0f0;border-radius:3px;padding:1px 5px;font-family:Menlo,Consolas,monospace;font-size:13px;"


def _code_to_br(match: re.Match) -> str:
    """코드 블록의 줄바꿈과 들여쓰기를 네이버 에디터가 지우지 못하는 태그로 바꾼다.

    네이버 에디터는 <pre> 안의 줄바꿈 문자와 연속 공백을 무시하는 경우가 있다.
    그래서 줄바꿈은 <br>, 줄 앞 들여쓰기는 &nbsp; 로 직접 적는다.
    """
    lines = match.group(2).rstrip("\n").split("\n")
    converted = []
    for line in lines:
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        rest = re.sub(r" {2,}", lambda m: "&nbsp;" * len(m.group()), stripped.replace("\t", " " * 4))
        converted.append("&nbsp;" * indent + rest)
    return f"{match.group(1)}{'<br>'.join(converted)}</code></pre>"


def to_html(md_text: str) -> str:
    body = markdown.markdown(md_text, extensions=["fenced_code", "sane_lists", "tables", "nl2br"])
    # 코드 블록 안의 <code> 는 pre 스타일을 따르게 하고, 인라인 <code> 에만 배경을 준다.
    body = re.sub(r"(<pre><code[^>]*>)(.*?)</code></pre>", _code_to_br, body, flags=re.S)
    body = re.sub(r"<pre><code([^>]*)>", r"<pre PRE_MARK><code\1>", body)
    body = re.sub(r"<code>(?!</)", f'<code style="{INLINE_CODE}">', body)
    for tag, style in STYLES.items():
        if tag == "pre":
            continue
        body = re.sub(rf"<{tag}>", f'<{tag} style="{style}">', body)
    body = body.replace("<pre PRE_MARK>", f'<pre style="{STYLES["pre"]}">')
    return (
        '<!doctype html>\n<html lang="ko"><head><meta charset="utf-8">'
        "<title>블로그 초안</title></head>\n"
        '<body style="max-width:720px;margin:32px auto;padding:0 16px;'
        'font-family:-apple-system,\'Apple SD Gothic Neo\',sans-serif;color:#222;">\n'
        f"{body}\n</body></html>\n"
    )


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--no-open"]
    if len(args) != 1 or not args[0].endswith(".md"):
        print("사용법: python src/render_draft.py drafts/<파일>.md [--no-open]", file=sys.stderr)
        return 2
    src = Path(args[0])
    if not src.exists():
        print(f"파일이 없다: {src}", file=sys.stderr)
        return 1
    out = src.with_suffix(".html")
    out.write_text(to_html(src.read_text(encoding="utf-8")), encoding="utf-8")
    print(f"만들었다: {out}")
    print("브라우저에서 전체 선택(Cmd+A) -> 복사(Cmd+C) -> 네이버 글쓰기에 붙여넣기(Cmd+V)")
    if "--no-open" not in argv and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
