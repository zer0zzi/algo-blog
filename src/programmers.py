"""프로그래머스 문제 등록.

프로그래머스는 스크래핑하지 않는다. 사용자가 문제 내용을 템플릿에 붙여 넣고,
이 스크립트가 백준과 같은 형태의 JSON 으로 변환해 problems/programmers/ 에 캐시한다.

사용법
  python src/programmers.py add <문제번호>
    - 템플릿(.md)이 없으면 만든다. 내용을 붙여 넣은 뒤 같은 명령을 다시 실행한다.
    - 템플릿이 채워져 있으면 JSON 으로 변환한다.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "problems" / "programmers"

SECTIONS = ["문제 설명", "제한사항", "입출력 예", "입출력 예 설명"]
META_KEYS = {"제목": "title", "레벨": "level", "유형": "tags"}

TEMPLATE = """제목: 
레벨: 
유형: 
URL: https://school.programmers.co.kr/learn/courses/30/lessons/{id}

## 문제 설명

## 제한사항

## 입출력 예

## 입출력 예 설명
"""


IMAGE_LINE = re.compile(r"^\s*\S.*\.(png|jpe?g|gif|webp|svg)\s*$", re.I)


def strip_images(text: str) -> tuple[str, int]:
    """이미지 파일명만 적힌 줄(복사할 때 딸려 오는 텍스트)을 제거하고, 제거한 개수를 반환한다."""
    kept, removed = [], 0
    for line in text.splitlines():
        if IMAGE_LINE.match(line):
            removed += 1
        else:
            kept.append(line)
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(kept)).strip()
    return cleaned, removed


def parse_template(text: str, problem_id: int) -> dict:
    head, *rest = re.split(r"^## ", text, flags=re.M)
    meta = {}
    for line in head.splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()

    sections = {}
    omitted_images = 0
    for block in rest:
        name, _, body = block.partition("\n")
        cleaned, removed = strip_images(body)
        sections[name.strip()] = cleaned
        omitted_images += removed

    missing = []
    if not meta.get("제목"):
        missing.append("제목")
    if not sections.get("문제 설명"):
        missing.append("문제 설명")
    if not sections.get("입출력 예"):
        missing.append("입출력 예")
    if missing:
        raise ValueError("비어 있는 항목: " + ", ".join(missing))

    tags = [t.strip() for t in re.split(r"[,/]", meta.get("유형", "")) if t.strip()]
    level = meta.get("레벨", "")
    return {
        "platform": "programmers",
        "id": problem_id,
        "title": meta["제목"],
        "url": meta.get("URL") or f"https://school.programmers.co.kr/learn/courses/30/lessons/{problem_id}",
        "level": level or None,
        "tags": tags,
        "description": sections["문제 설명"],
        "constraints": sections.get("제한사항", ""),
        "examples": sections["입출력 예"],
        "example_notes": sections.get("입출력 예 설명", ""),
        "omitted_images": omitted_images,
    }


def add(problem_id: int) -> int:
    DIR.mkdir(parents=True, exist_ok=True)
    md_path = DIR / f"{problem_id}.md"
    json_path = DIR / f"{problem_id}.json"

    if not md_path.exists():
        md_path.write_text(TEMPLATE.format(id=problem_id), encoding="utf-8")
        print(f"템플릿을 만들었다: {md_path.relative_to(ROOT)}")
        print("문제 페이지의 내용을 붙여 넣고 저장한 뒤, 같은 명령을 다시 실행한다.")
        return 0

    try:
        problem = parse_template(md_path.read_text(encoding="utf-8"), problem_id)
    except ValueError as e:
        print(f"변환 실패: {e}\n{md_path.relative_to(ROOT)} 를 채우고 다시 실행한다.", file=sys.stderr)
        return 1

    json_path.write_text(json.dumps(problem, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[등록] 프로그래머스 {problem['id']}번 {problem['title']}")
    print(f"  레벨 {problem['level'] or '미입력'} / 유형 {', '.join(problem['tags']) or '미입력'}")
    if problem["omitted_images"]:
        print(f"  이미지 파일명 {problem['omitted_images']}줄 제거 (이미지 내용은 텍스트 설명으로만 반영됨)")
    print(f"  저장: {json_path.relative_to(ROOT)}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3 or argv[1] != "add" or not re.fullmatch(r"\d+", argv[2]):
        print("사용법: python src/programmers.py add <문제번호>", file=sys.stderr)
        return 2
    return add(int(argv[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
