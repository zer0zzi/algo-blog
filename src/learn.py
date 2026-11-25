"""학습 모드: 문제를 분석해서 알아 둘 알고리즘 개념과 문제 유형을 정리한다.

풀이 전에 보는 용도라서 정답 코드나 풀이 단계는 출력하지 않는다. (힌트는 코치 모드 담당)

사용법
  python src/learn.py boj <문제번호> [--force]
  python src/learn.py programmers <문제번호> [--force]

- 결과는 problems/<플랫폼>/<번호>.learn.json 에 캐시한다. (--force 로 다시 생성)
- ANTHROPIC_API_KEY 는 환경변수 또는 프로젝트 루트의 .env 에서 읽는다.
"""
import json
import os
import sys
from pathlib import Path

import anthropic

ROOT = Path(__file__).resolve().parent.parent
MODEL = "claude-sonnet-5-5"  # 비용 절감용. 품질이 아쉬우면 claude-opus-5-5 로 바꾼다.

SYSTEM_PROMPT = """당신은 코딩테스트를 준비하는 학습자를 돕는 알고리즘 코치다.
주어진 문제를 분석해서, 학습자가 외우고 알아 두면 좋은 개념과 문제 유형을 정리한다.

규칙
- 이 분석은 풀이 전에 읽는다. 정답 코드, 단계별 풀이, 문제의 정답 자체를 쓰지 않는다.
  개념과 유형 수준에서만 설명하고, 이 문제에 곧바로 쓰는 방법은 한 단계 추상화해서 말한다.
- 시간복잡도 판단은 제한사항의 숫자(N, 시간 제한)를 근거로 계산해서 쓴다. 추측으로 쓰지 않는다.
- 확실하지 않은 내용은 지어내지 말고 needs_check 에 "확인 필요: ..." 형태로 적는다.
- 문제에 알고리즘 태그가 이미 있으면 그것을 우선 근거로 삼는다. 태그가 비어 있어서 추정한 것이면
  needs_check 에 "알고리즘 유형은 추정값, 확인 필요"를 넣는다.
- 문제 원문을 그대로 옮겨 쓰지 않는다. 직접 쓴 표현으로 요약한다.
- 한국어 평어체(~이다, ~한다)로, 간결하게 쓴다.
"""

SCHEMA = {
    "type": "object",
    "properties": {
        "problem_type": {"type": "string", "description": "문제 유형 한 줄 요약"},
        "algorithm_tags": {"type": "array", "items": {"type": "string"}},
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "summary": {"type": "string", "description": "처음 보는 사람도 이해할 수준의 2~3문장"},
                    "memorize": {"type": "array", "items": {"type": "string"}, "description": "외워 둘 핵심 포인트"},
                    "complexity": {"type": "string", "description": "대표 시간복잡도와 근거 한 줄"},
                },
                "required": ["name", "summary", "memorize", "complexity"],
                "additionalProperties": False,
            },
        },
        "constraint_analysis": {"type": "string", "description": "제한사항 숫자로 본 허용 시간복잡도 계산"},
        "recognition_signals": {"type": "array", "items": {"type": "string"}, "description": "이 유형을 알아보는 단서"},
        "common_pitfalls": {"type": "array", "items": {"type": "string"}},
        "related_problem_types": {"type": "array", "items": {"type": "string"}},
        "needs_check": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "problem_type", "algorithm_tags", "concepts", "constraint_analysis",
        "recognition_signals", "common_pitfalls", "related_problem_types", "needs_check",
    ],
    "additionalProperties": False,
}


def load_env() -> None:
    """프로젝트 루트의 .env 를 읽어 환경변수에 넣는다. (이미 있는 값은 덮어쓰지 않는다)"""
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_problem(platform: str, problem_id: int) -> dict:
    path = ROOT / "problems" / platform / f"{problem_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if platform == "boj":
        import boj  # 캐시가 없으면 백준에서 1개만 가져온다
        return boj.get_problem(problem_id)[0]
    raise FileNotFoundError(
        f"{path.relative_to(ROOT)} 가 없다. 먼저 `python src/programmers.py add {problem_id}` 로 등록한다."
    )


def build_user_prompt(problem: dict) -> str:
    parts = [f"플랫폼: {problem['platform']}", f"제목: {problem['title']}"]
    if problem.get("level") is not None:
        parts.append(f"난이도: {problem['level']}")
    tags = problem.get("tags") or []
    parts.append(f"알고리즘 태그: {', '.join(tags) if tags else '(없음, 추정 필요)'}")
    if problem.get("time_limit"):
        parts.append(f"시간 제한: {problem['time_limit']} / 메모리 제한: {problem['memory_limit']}")
    parts.append(f"\n[문제 설명]\n{problem['description']}")
    if problem["platform"] == "boj":
        parts.append(f"\n[입력]\n{problem['input']}\n\n[출력]\n{problem['output']}")
    else:
        parts.append(f"\n[제한사항]\n{problem.get('constraints', '')}")
        parts.append(f"\n[입출력 예]\n{problem.get('examples', '')}")
        parts.append(f"\n[입출력 예 설명]\n{problem.get('example_notes', '')}")
    if problem.get("omitted_images"):
        parts.append(
            f"\n(참고: 원문에서 이미지 {problem['omitted_images']}개가 빠졌다. "
            "설명이 이미지에 의존해 보이면 needs_check 에 '이미지 내용 확인 필요'를 적는다.)"
        )
    return "\n".join(parts)


def analyze(problem: dict) -> dict:
    client = anthropic.Anthropic()
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",  # 안전 분류기가 거절하면 서버가 대체 모델로 재시도한다
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(problem)}],
    )
    if response.stop_reason == "refusal":
        raise RuntimeError("모델이 응답을 거절했다. 문제 내용을 확인한다.")
    if response.stop_reason == "max_tokens":
        raise RuntimeError("응답이 max_tokens 에서 잘렸다.")
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)


def render(problem: dict, notes: dict) -> str:
    lines = [f"# {problem['title']} ({problem['platform']} {problem['id']})", ""]
    lines += [f"**유형**: {notes['problem_type']}", f"**알고리즘**: {', '.join(notes['algorithm_tags']) or '-'}", ""]
    lines += ["## 알아 둘 개념"]
    for c in notes["concepts"]:
        lines += [f"### {c['name']}", c["summary"], ""]
        lines += [f"- {m}" for m in c["memorize"]]
        lines += [f"- 복잡도: {c['complexity']}", ""]
    lines += ["## 제한사항으로 본 복잡도", notes["constraint_analysis"], ""]
    lines += ["## 이런 문제를 알아보는 단서"] + [f"- {s}" for s in notes["recognition_signals"]] + [""]
    lines += ["## 자주 하는 실수"] + [f"- {s}" for s in notes["common_pitfalls"]] + [""]
    lines += ["## 비슷한 유형"] + [f"- {s}" for s in notes["related_problem_types"]] + [""]
    if notes["needs_check"]:
        lines += ["## 확인 필요"] + [f"- {s}" for s in notes["needs_check"]]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--force"]
    force = "--force" in argv
    if len(args) != 2 or args[0] not in ("boj", "programmers") or not args[1].isdigit():
        print("사용법: python src/learn.py <boj|programmers> <문제번호> [--force]", file=sys.stderr)
        return 2
    platform, problem_id = args[0], int(args[1])

    try:
        problem = load_problem(platform, problem_id)
    except FileNotFoundError as e:
        print(e, file=sys.stderr)
        return 1

    cache = ROOT / "problems" / platform / f"{problem_id}.learn.json"
    if cache.exists() and not force:
        notes = json.loads(cache.read_text(encoding="utf-8"))
        print("(저장된 분석을 불러왔다. 다시 만들려면 --force)\n", file=sys.stderr)
    else:
        load_env()
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY 가 없다. 프로젝트 루트 .env 에 ANTHROPIC_API_KEY=... 를 넣는다.", file=sys.stderr)
            return 1
        try:
            notes = analyze(problem)
        except anthropic.APIError as e:
            print(f"API 오류: {e}", file=sys.stderr)
            return 1
        except RuntimeError as e:
            print(e, file=sys.stderr)
            return 1
        cache.write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(render(problem, notes))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
