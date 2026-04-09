"""
Claude API 호출 및 문제 생성 로직
수준별 맞춤 물리 문제를 Claude AI를 통해 생성한다.
"""

import json
import logging
import os
import threading
import time
from typing import Callable, Optional

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 한국 고등학교/대학교 물리 전문 출제 교수입니다.
학생 수준에 맞는 물리 문제를 JSON 형식으로만 반환합니다.

반환 JSON 형식:
{
  "problems": [
    {
      "number": 1,
      "type": "객관식|단답형|서술형|계산",
      "question": "문제 내용 (수식은 LaTeX 형식)",
      "options": ["①...", "②...", "③...", "④...", "⑤..."],
      "answer": "정답",
      "explanation": "풀이 및 해설",
      "difficulty": "상|중|하",
      "estimated_time": "분 단위"
    }
  ],
  "level_summary": "이 수준 학생들을 위한 학습 안내"
}

중요 규칙:
- options 필드는 객관식 문제에만 포함합니다. 다른 유형에서는 이 필드를 생략하세요.
- 수식은 반드시 LaTeX 형식으로 작성합니다 (예: $v = v_0 + at$).
- 문제는 한국어로 작성합니다.
- JSON만 반환하고, 다른 텍스트는 포함하지 마세요."""

LEVEL_PROMPTS = {
    "advanced": (
        "수능 1등급 수준의 심화 문제를 출제하세요.\n"
        "- 복합 개념 적용이 필요한 문제\n"
        "- 그래프 분석, 실험 설계 해석 포함\n"
        "- 고난도 계산 및 추론 능력 요구\n"
        "- 실생활 응용 및 융합 문제 포함"
    ),
    "standard": (
        "수능 3-4등급 수준의 표준 문제를 출제하세요.\n"
        "- 개념 확인 및 기본 응용 문제\n"
        "- 공식 적용 및 간단한 계산 문제\n"
        "- 핵심 개념의 이해도를 확인하는 문제\n"
        "- 적절한 난이도 배분"
    ),
    "remedial": (
        "기초 수준의 보충 문제를 출제하세요.\n"
        "- 기초 개념 반복 확인 문제\n"
        "- 단계별 풀이가 유도되는 문제\n"
        "- 핵심 공식과 개념을 직접 적용하는 문제\n"
        "- 힌트를 포함한 문제 (풀이 방향 제시)\n"
        "- 자신감을 줄 수 있는 난이도"
    ),
}

SUBJECTS = [
    "통합과학",
    "물리학",
    "물질과 에너지",
    "전자기와 양자",
    "일반물리학",
]


class AIEngine:
    """Claude API를 사용하여 수준별 물리 문제를 생성하는 엔진"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.api_key = api_key
        self.model = model
        self.client = anthropic.Anthropic(api_key=api_key)
        self._cancel_event = threading.Event()

    def test_connection(self) -> bool:
        """API 연결을 테스트한다."""
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=50,
                messages=[{"role": "user", "content": "테스트입니다. '연결 성공'이라고만 답하세요."}],
            )
            text = response.content[0].text
            logger.info(f"API 연결 테스트 성공: {text}")
            return True
        except Exception as e:
            logger.error(f"API 연결 테스트 실패: {e}")
            raise

    def list_models(self) -> list:
        """사용 가능한 모델 목록을 반환한다."""
        return [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
        ]

    def generate_problems(
        self,
        level: str,
        subject: str,
        unit: str,
        problem_types: list,
        count: int,
        avg_score: float,
        show_hints: bool = False,
    ) -> dict:
        """
        수준별 맞춤 문제를 생성한다.

        Args:
            level: "advanced" / "standard" / "remedial"
            subject: 과목명
            unit: 단원명
            problem_types: 문제 유형 리스트
            count: 문제 수
            avg_score: 해당 수준 학생들의 평균 점수
            show_hints: 힌트 표시 여부

        Returns:
            {"problems": [...], "level_summary": "..."}
        """
        if self._cancel_event.is_set():
            return {"problems": [], "level_summary": "생성 취소됨"}

        level_prompt = LEVEL_PROMPTS.get(level, LEVEL_PROMPTS["standard"])

        type_str = ", ".join(problem_types)
        hint_instruction = ""
        if show_hints or level == "remedial":
            hint_instruction = "\n- 각 문제에 풀이 힌트를 포함하세요."

        user_prompt = (
            f"과목: {subject}\n"
            f"단원: {unit}\n"
            f"학생 수준: {level} (평균 점수: {avg_score}점)\n"
            f"문제 유형: {type_str}\n"
            f"문제 수: {count}문항\n\n"
            f"{level_prompt}\n"
            f"{hint_instruction}\n\n"
            f"위 조건에 맞는 {count}개의 물리 문제를 JSON 형식으로 생성하세요."
        )

        max_retries = 3
        for attempt in range(max_retries):
            if self._cancel_event.is_set():
                return {"problems": [], "level_summary": "생성 취소됨"}
            try:
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=8000,
                    system=SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                text = response.content[0].text.strip()
                # JSON 파싱 - 코드 블록 제거
                if text.startswith("```"):
                    lines = text.split("\n")
                    text = "\n".join(lines[1:])
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()

                result = json.loads(text)
                logger.info(f"[{level}] 문제 생성 완료: {len(result.get('problems', []))}문항")
                return result

            except json.JSONDecodeError as e:
                logger.warning(f"[{level}] JSON 파싱 실패 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise ValueError(f"AI 응답을 파싱할 수 없습니다: {e}")
            except anthropic.APIError as e:
                logger.warning(f"[{level}] API 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        return {"problems": [], "level_summary": "생성 실패"}

    def generate_all_levels(
        self,
        levels_config: dict,
        subject: str,
        unit: str,
        problem_types: list,
        show_hints: bool = False,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
    ) -> dict:
        """
        모든 수준의 문제를 병렬로 생성한다.

        Args:
            levels_config: {level: {"count": N, "avg_score": float}}
            subject: 과목명
            unit: 단원명
            problem_types: 문제 유형 리스트
            show_hints: 힌트 표시 여부
            progress_callback: 진행률 콜백 (level, progress_0_to_1)
            log_callback: 로그 콜백 (message)

        Returns:
            {level: {"problems": [...], "level_summary": "..."}}
        """
        self._cancel_event.clear()
        results = {}
        errors = {}

        def _generate_for_level(level, config):
            level_kr = {"advanced": "심화", "standard": "표준", "remedial": "보충"}.get(level, level)
            try:
                if log_callback:
                    log_callback(f"[{level_kr}] 문제 생성 시작 ({config['count']}문항)...")
                if progress_callback:
                    progress_callback(level, 0.1)

                result = self.generate_problems(
                    level=level,
                    subject=subject,
                    unit=unit,
                    problem_types=problem_types,
                    count=config["count"],
                    avg_score=config.get("avg_score", 50),
                    show_hints=show_hints,
                )
                results[level] = result

                if progress_callback:
                    progress_callback(level, 1.0)
                if log_callback:
                    n = len(result.get("problems", []))
                    log_callback(f"[{level_kr}] 완료! {n}문항 생성됨")

            except Exception as e:
                errors[level] = str(e)
                if log_callback:
                    log_callback(f"[{level_kr}] 오류 발생: {e}")
                if progress_callback:
                    progress_callback(level, -1)

        threads = []
        for level, config in levels_config.items():
            t = threading.Thread(target=_generate_for_level, args=(level, config))
            t.daemon = True
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        if errors:
            logger.error(f"문제 생성 오류: {errors}")

        return results

    def cancel(self):
        """진행 중인 생성을 취소한다."""
        self._cancel_event.set()
        logger.info("문제 생성 취소 요청됨")

    def save_cache(self, results: dict, cache_dir: str = "output/cache"):
        """생성 결과를 캐시 파일로 저장한다."""
        os.makedirs(cache_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(cache_dir, f"problems_{timestamp}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        logger.info(f"캐시 저장 완료: {filepath}")
        return filepath

    def load_cache(self, filepath: str) -> dict:
        """캐시 파일에서 생성 결과를 불러온다."""
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
