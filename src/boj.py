"""백준 문제 가져오기.

규칙
- 한 번 실행에 문제 1개만 가져온다. (여러 개 일괄 수집 금지)
- 이미 캐시가 있으면 요청을 보내지 않는다.
- 요청 사이에는 최소 간격(MIN_INTERVAL)을 둔다. 실행 간에도 지켜지도록 시각을 파일에 기록한다.
- 문제 원문은 problems/ 에 저장하고, problems/ 는 git 에 올리지 않는다.
"""
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "problems" / "boj"
LAST_REQUEST_FILE = ROOT / "problems" / ".last_request"
MIN_INTERVAL = 2.0  # 초. 요청 사이 최소 간격
HEADERS = {"User-Agent": "algo-blog-study-tool/0.1 (personal use)"}


def _wait_for_interval() -> None:
    """직전 요청(이전 실행 포함)으로부터 MIN_INTERVAL 이 지나도록 기다린다."""
    try:
        last = float(LAST_REQUEST_FILE.read_text())
    except (FileNotFoundError, ValueError):
        last = 0.0
    remaining = MIN_INTERVAL - (time.time() - last)
    if remaining > 0:
        time.sleep(remaining)


def _get(url: str) -> requests.Response:
    _wait_for_interval()
    LAST_REQUEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
    finally:
        LAST_REQUEST_FILE.write_text(str(time.time()))
    return resp


def _text(soup: BeautifulSoup, selector: str) -> str:
    el = soup.select_one(selector)
    return el.get_text("\n", strip=True) if el else ""


def _parse_problem(html: str, problem_id: int) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = _text(soup, "#problem_title")
    if not title:
        raise ValueError("문제 제목을 찾지 못했다. 페이지 구조가 바뀌었거나 접근이 차단됐을 수 있다.")

    info = {}
    headers = [th.get_text(strip=True) for th in soup.select("#problem-info thead th")]
    values = [td.get_text(strip=True) for td in soup.select("#problem-info tbody td")]
    for h, v in zip(headers, values):
        info[h] = v

    samples = []
    i = 1
    while True:
        sin = soup.select_one(f"#sample-input-{i}")
        sout = soup.select_one(f"#sample-output-{i}")
        if not sin or not sout:
            break
        samples.append({"input": sin.get_text(), "output": sout.get_text()})
        i += 1

    return {
        "platform": "boj",
        "id": problem_id,
        "title": title,
        "url": f"https://www.acmicpc.net/problem/{problem_id}",
        "time_limit": info.get("시간 제한", ""),
        "memory_limit": info.get("메모리 제한", ""),
        "description": _text(soup, "#problem_description"),
        "input": _text(soup, "#problem_input"),
        "output": _text(soup, "#problem_output"),
        "samples": samples,
    }


def _fetch_meta(problem_id: int) -> dict:
    """solved.ac 에서 난이도와 알고리즘 태그를 가져온다.

    solved.ac 는 자동 요청을 Cloudflare 로 막는 경우가 있다. 막히면 우회하지 않고 빈 값을 반환한다.
    (태그는 AI 분석 단계에서 추정하되 '확인 필요'로 표시한다.)
    """
    try:
        resp = _get(f"https://solved.ac/api/v3/problem/show?problemId={problem_id}")
        if resp.status_code != 200:
            return {}
        data = resp.json()
        tags = []
        for t in data.get("tags", []):
            names = {n["language"]: n["name"] for n in t.get("displayNames", [])}
            tags.append(names.get("ko") or names.get("en") or t["key"])
        return {"level": data.get("level"), "tags": tags}
    except (requests.RequestException, ValueError):
        return {}


def get_problem(problem_id: int) -> tuple[dict, bool]:
    """(문제 데이터, 캐시 사용 여부)를 반환한다."""
    path = CACHE_DIR / f"{problem_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")), True

    resp = _get(f"https://www.acmicpc.net/problem/{problem_id}")
    if resp.status_code != 200:
        raise RuntimeError(f"백준 요청 실패: HTTP {resp.status_code}")
    problem = _parse_problem(resp.text, problem_id)
    problem.update(_fetch_meta(problem_id))

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(problem, ensure_ascii=False, indent=2), encoding="utf-8")
    return problem, False


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not re.fullmatch(r"\d+", argv[1]):
        print("사용법: python src/boj.py <문제번호>   (한 번에 1개만 가져온다)", file=sys.stderr)
        return 2
    problem, cached = get_problem(int(argv[1]))
    src = "캐시" if cached else "백준"
    print(f"[{src}] 백준 {problem['id']}번 {problem['title']}")
    print(f"  시간 {problem['time_limit']} / 메모리 {problem['memory_limit']}")
    print(f"  난이도(solved.ac) {problem.get('level', '가져오지 못함')} / 태그 {', '.join(problem.get('tags', [])) or '가져오지 못함'}")
    print(f"  예제 {len(problem['samples'])}개 저장: problems/boj/{problem['id']}.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
