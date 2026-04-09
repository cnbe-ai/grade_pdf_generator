"""
성적 데이터 분석 및 수준 분류 모듈
Excel/CSV 파일에서 성적 데이터를 읽어 학생별 수준을 분류한다.
"""

import pandas as pd
import numpy as np
import os
import logging

logger = logging.getLogger(__name__)


class GradeAnalyzer:
    """학생 성적 데이터를 분석하고 수준별로 분류하는 클래스"""

    LEVEL_ADVANCED = "advanced"    # 심화 (1등급)
    LEVEL_STANDARD = "standard"    # 표준 (2등급)
    LEVEL_REMEDIAL = "remedial"    # 보충 (3등급)

    LEVEL_NAMES_KR = {
        LEVEL_ADVANCED: "심화",
        LEVEL_STANDARD: "표준",
        LEVEL_REMEDIAL: "보충",
    }

    def __init__(self, advanced_pct: int = 30, remedial_pct: int = 30):
        """
        Args:
            advanced_pct: 상위 N% 를 심화로 분류 (기본 30)
            remedial_pct: 하위 N% 를 보충으로 분류 (기본 30)
        """
        self.advanced_pct = advanced_pct
        self.remedial_pct = remedial_pct
        self.df = None
        self.name_col = None
        self.score_col = None

    def load_file(self, filepath: str) -> pd.DataFrame:
        """Excel 또는 CSV 파일을 불러온다."""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == ".csv":
            self.df = pd.read_csv(filepath, encoding="utf-8-sig")
        elif ext in (".xlsx", ".xls"):
            self.df = pd.read_excel(filepath, engine="openpyxl")
        else:
            raise ValueError(f"지원하지 않는 파일 형식입니다: {ext}\n지원 형식: .xlsx, .xls, .csv")
        logger.info(f"파일 로드 완료: {filepath} ({len(self.df)}행)")
        return self.df

    def get_columns(self) -> list:
        """현재 로드된 데이터의 컬럼 목록을 반환한다."""
        if self.df is None:
            return []
        return list(self.df.columns)

    def set_column_mapping(self, name_col: str, score_col: str):
        """학생이름 컬럼과 점수 컬럼을 매핑한다."""
        if self.df is None:
            raise RuntimeError("먼저 파일을 로드하세요.")
        if name_col not in self.df.columns:
            raise ValueError(f"컬럼 '{name_col}'이(가) 데이터에 없습니다.")
        if score_col not in self.df.columns:
            raise ValueError(f"컬럼 '{score_col}'이(가) 데이터에 없습니다.")
        self.name_col = name_col
        self.score_col = score_col
        # 점수 컬럼을 숫자로 변환
        self.df[score_col] = pd.to_numeric(self.df[score_col], errors="coerce")
        invalid_count = self.df[score_col].isna().sum()
        if invalid_count > 0:
            logger.warning(f"숫자로 변환할 수 없는 점수 {invalid_count}개 발견 (NaN 처리됨)")

    def classify_students(self) -> pd.DataFrame:
        """학생들을 수준별로 분류한다."""
        if self.df is None or self.name_col is None or self.score_col is None:
            raise RuntimeError("파일을 로드하고 컬럼을 매핑하세요.")

        df = self.df.dropna(subset=[self.score_col]).copy()
        scores = df[self.score_col]

        # 백분위 기준 계산
        advanced_threshold = np.percentile(scores, 100 - self.advanced_pct)
        remedial_threshold = np.percentile(scores, self.remedial_pct)

        def assign_level(score):
            if score >= advanced_threshold:
                return self.LEVEL_ADVANCED
            elif score <= remedial_threshold:
                return self.LEVEL_REMEDIAL
            else:
                return self.LEVEL_STANDARD

        df["level"] = scores.apply(assign_level)
        df["level_kr"] = df["level"].map(self.LEVEL_NAMES_KR)

        self.df = df
        logger.info(
            f"수준 분류 완료 - "
            f"심화: {(df['level'] == self.LEVEL_ADVANCED).sum()}명, "
            f"표준: {(df['level'] == self.LEVEL_STANDARD).sum()}명, "
            f"보충: {(df['level'] == self.LEVEL_REMEDIAL).sum()}명"
        )
        return df

    def get_level_stats(self) -> dict:
        """수준별 통계를 반환한다."""
        if self.df is None or "level" not in self.df.columns:
            return {}
        stats = {}
        for level in [self.LEVEL_ADVANCED, self.LEVEL_STANDARD, self.LEVEL_REMEDIAL]:
            group = self.df[self.df["level"] == level]
            if len(group) > 0:
                stats[level] = {
                    "count": len(group),
                    "avg_score": round(group[self.score_col].mean(), 1),
                    "min_score": round(group[self.score_col].min(), 1),
                    "max_score": round(group[self.score_col].max(), 1),
                    "students": list(group[self.name_col]),
                }
            else:
                stats[level] = {
                    "count": 0,
                    "avg_score": 0,
                    "min_score": 0,
                    "max_score": 0,
                    "students": [],
                }
        return stats

    def get_classified_data(self) -> list:
        """분류된 학생 데이터를 리스트로 반환한다 (GUI 테이블용)."""
        if self.df is None or "level" not in self.df.columns:
            return []
        rows = []
        for _, row in self.df.iterrows():
            rows.append({
                "name": row[self.name_col],
                "score": row[self.score_col],
                "level": row["level"],
                "level_kr": row["level_kr"],
            })
        return sorted(rows, key=lambda x: x["score"], reverse=True)


def generate_sample_data(output_path: str = "sample_data/sample_scores.xlsx"):
    """테스트용 샘플 성적 데이터를 생성한다."""
    np.random.seed(42)
    names = [
        "김민준", "이서연", "박지호", "최수아", "정예준",
        "강하은", "조민서", "윤지우", "장서준", "임하린",
        "한도윤", "오시은", "신지안", "권하준", "송지유",
        "류현우", "문서영", "배준서", "홍다은", "황지훈",
        "전소율", "나윤아", "구민재", "유서현", "양태현",
        "백지민", "서연우", "노하영", "곽승현", "진예은",
    ]
    scores = np.random.normal(loc=65, scale=18, size=30)
    scores = np.clip(scores, 0, 100).round(0).astype(int)

    df = pd.DataFrame({"학생이름": names, "점수": scores})

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")
    logger.info(f"샘플 데이터 생성 완료: {output_path}")
    return output_path
