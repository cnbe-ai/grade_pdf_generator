"""
PDF 레이아웃 및 생성 모듈
reportlab을 사용하여 수준별 맞춤 문제지와 답안지를 PDF로 생성한다.
"""

import io
import logging
import os
import re
import time
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm, cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_NAME = "NanumGothic"
FONT_FILE = "NanumGothic.ttf"

LEVEL_COLORS = {
    "advanced": colors.HexColor("#1565C0"),   # 파란색
    "standard": colors.HexColor("#F57F17"),    # 주황색
    "remedial": colors.HexColor("#2E7D32"),    # 초록색
}

LEVEL_TITLES = {
    "advanced": "심화 학습 자료",
    "standard": "표준 학습 자료",
    "remedial": "보충 학습 자료",
}

PAGE_WIDTH, PAGE_HEIGHT = A4


def ensure_font():
    """한글 폰트를 등록한다. 없으면 다운로드를 시도한다."""
    font_path = os.path.join(FONT_DIR, FONT_FILE)

    if not os.path.exists(font_path):
        os.makedirs(FONT_DIR, exist_ok=True)
        try:
            import requests
            url = "https://github.com/google/fonts/raw/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
            logger.info(f"한글 폰트 다운로드 중: {url}")
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            with open(font_path, "wb") as f:
                f.write(resp.content)
            logger.info("한글 폰트 다운로드 완료")
        except Exception as e:
            logger.warning(f"폰트 다운로드 실패: {e}. 시스템 폰트를 찾습니다.")
            # 시스템에서 한글 폰트 검색
            for sys_path in [
                "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
                "/usr/share/fonts/nanum/NanumGothic.ttf",
                "C:/Windows/Fonts/malgun.ttf",
                "C:/Windows/Fonts/NanumGothic.ttf",
            ]:
                if os.path.exists(sys_path):
                    font_path = sys_path
                    break
            else:
                logger.error("한글 폰트를 찾을 수 없습니다. fonts/ 폴더에 NanumGothic.ttf를 넣어주세요.")
                return False

    try:
        pdfmetrics.registerFont(TTFont(FONT_NAME, font_path))
        pdfmetrics.registerFont(TTFont(FONT_NAME + "-Bold", font_path))
        # matplotlib에도 등록
        fm.fontManager.addfont(font_path)
        plt.rcParams["font.family"] = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams["axes.unicode_minus"] = False
        logger.info(f"폰트 등록 완료: {font_path}")
        return True
    except Exception as e:
        logger.error(f"폰트 등록 실패: {e}")
        return False


def _get_styles():
    """PDF 스타일 정의"""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name="KoreanTitle",
        fontName=FONT_NAME,
        fontSize=22,
        leading=28,
        alignment=TA_CENTER,
        spaceAfter=12,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="KoreanSubtitle",
        fontName=FONT_NAME,
        fontSize=14,
        leading=18,
        alignment=TA_CENTER,
        spaceAfter=8,
        textColor=colors.white,
    ))
    styles.add(ParagraphStyle(
        name="KoreanBody",
        fontName=FONT_NAME,
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="KoreanBodyJustify",
        fontName=FONT_NAME,
        fontSize=11,
        leading=16,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="QuestionNumber",
        fontName=FONT_NAME,
        fontSize=12,
        leading=16,
        alignment=TA_LEFT,
        spaceBefore=12,
        spaceAfter=4,
        textColor=colors.HexColor("#333333"),
    ))
    styles.add(ParagraphStyle(
        name="QuestionText",
        fontName=FONT_NAME,
        fontSize=11,
        leading=16,
        alignment=TA_LEFT,
        leftIndent=20,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="OptionText",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=30,
        spaceAfter=2,
    ))
    styles.add(ParagraphStyle(
        name="HintBox",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=20,
        rightIndent=20,
        spaceBefore=4,
        spaceAfter=8,
        textColor=colors.HexColor("#1B5E20"),
        backColor=colors.HexColor("#E8F5E9"),
        borderPadding=8,
    ))
    styles.add(ParagraphStyle(
        name="AnswerHeader",
        fontName=FONT_NAME,
        fontSize=13,
        leading=18,
        alignment=TA_LEFT,
        spaceBefore=10,
        spaceAfter=4,
        textColor=colors.HexColor("#B71C1C"),
    ))
    styles.add(ParagraphStyle(
        name="AnswerText",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=20,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="ExplanationText",
        fontName=FONT_NAME,
        fontSize=10,
        leading=14,
        alignment=TA_LEFT,
        leftIndent=20,
        spaceAfter=8,
        textColor=colors.HexColor("#333333"),
    ))
    styles.add(ParagraphStyle(
        name="PageInfo",
        fontName=FONT_NAME,
        fontSize=9,
        leading=12,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#666666"),
    ))
    styles.add(ParagraphStyle(
        name="SectionHeader",
        fontName=FONT_NAME,
        fontSize=14,
        leading=18,
        alignment=TA_LEFT,
        spaceBefore=16,
        spaceAfter=8,
        textColor=colors.HexColor("#212121"),
    ))
    return styles


def _latex_to_image(latex_str: str, fontsize: int = 14) -> Optional[str]:
    """LaTeX 수식을 이미지로 변환한다."""
    try:
        fig, ax = plt.subplots(figsize=(0.01, 0.01))
        ax.axis("off")
        text = ax.text(
            0, 0, f"${latex_str}$",
            fontsize=fontsize,
            verticalalignment="center",
        )
        fig.patch.set_alpha(0)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    pad_inches=0.05, transparent=True)
        plt.close(fig)
        buf.seek(0)
        return buf
    except Exception as e:
        logger.warning(f"LaTeX 렌더링 실패: {latex_str} -> {e}")
        return None


def _escape_xml(text: str) -> str:
    """XML 특수문자를 이스케이프한다."""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _process_text_with_latex(text: str, styles) -> list:
    """텍스트에서 LaTeX 수식을 찾아 이미지로 변환하고 flowable 목록을 반환한다."""
    elements = []
    # $...$ 패턴 찾기
    parts = re.split(r'(\$[^$]+\$)', text)
    combined_text = ""
    for part in parts:
        if part.startswith("$") and part.endswith("$"):
            latex = part[1:-1]
            img_buf = _latex_to_image(latex)
            if img_buf:
                if combined_text:
                    elements.append(Paragraph(_escape_xml(combined_text), styles["QuestionText"]))
                    combined_text = ""
                img = Image(img_buf, width=None, height=8 * mm)
                img.hAlign = "LEFT"
                elements.append(img)
            else:
                combined_text += part
        else:
            combined_text += part
    if combined_text:
        elements.append(Paragraph(_escape_xml(combined_text), styles["QuestionText"]))
    return elements


class PDFBuilder:
    """수준별 문제지와 답안지 PDF를 생성하는 클래스"""

    def __init__(self, school_name: str = "", teacher_name: str = ""):
        self.school_name = school_name
        self.teacher_name = teacher_name
        self.font_ready = ensure_font()
        self.styles = _get_styles()

    def _build_cover_page(self, level: str, subject: str, unit: str,
                          class_name: str = "") -> list:
        """표지 페이지를 구성한다."""
        elements = []
        level_color = LEVEL_COLORS.get(level, colors.grey)
        title = LEVEL_TITLES.get(level, "학습 자료")
        date_str = time.strftime("%Y년 %m월 %d일")

        # 상단 컬러 헤더 배경 테이블
        header_data = [[""]]
        header_table = Table(header_data, colWidths=[PAGE_WIDTH - 40 * mm],
                             rowHeights=[80 * mm])
        header_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), level_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

        elements.append(Spacer(1, 30 * mm))

        # 타이틀 블록
        title_data = [
            [Paragraph(f"<b>{_escape_xml(title)}</b>", self.styles["KoreanTitle"])],
            [Spacer(1, 5 * mm)],
            [Paragraph(_escape_xml(f"{subject} - {unit}"), self.styles["KoreanSubtitle"])],
        ]
        title_table = Table(title_data, colWidths=[PAGE_WIDTH - 40 * mm])
        title_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), level_color),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 20),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
            ("LEFTPADDING", (0, 0), (-1, -1), 15),
            ("RIGHTPADDING", (0, 0), (-1, -1), 15),
        ]))
        elements.append(title_table)
        elements.append(Spacer(1, 20 * mm))

        # 정보 테이블
        info_rows = []
        if self.school_name:
            info_rows.append(["학교", self.school_name])
        if class_name:
            info_rows.append(["학급", class_name])
        if self.teacher_name:
            info_rows.append(["출제자", self.teacher_name])
        info_rows.append(["날짜", date_str])
        info_rows.append(["과목", f"{subject} / {unit}"])

        if info_rows:
            info_para_rows = []
            for label, value in info_rows:
                info_para_rows.append([
                    Paragraph(f"<b>{_escape_xml(label)}</b>", self.styles["KoreanBody"]),
                    Paragraph(_escape_xml(value), self.styles["KoreanBody"]),
                ])
            info_table = Table(info_para_rows, colWidths=[30 * mm, 100 * mm])
            info_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDBDBD")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F5F5F5")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ]))
            elements.append(info_table)

        elements.append(PageBreak())
        return elements

    def _build_problem_pages(self, problems: list, level: str,
                             level_summary: str = "") -> list:
        """문제지 페이지를 구성한다."""
        elements = []
        level_color = LEVEL_COLORS.get(level, colors.grey)
        title = LEVEL_TITLES.get(level, "학습 자료")

        # 섹션 헤더
        elements.append(Paragraph(
            f"<b>{_escape_xml(title)} - 문제지</b>",
            self.styles["SectionHeader"],
        ))

        if level_summary:
            elements.append(Paragraph(
                _escape_xml(level_summary),
                self.styles["KoreanBody"],
            ))
            elements.append(Spacer(1, 5 * mm))

        for prob in problems:
            number = prob.get("number", "")
            p_type = prob.get("type", "")
            question = prob.get("question", "")
            options = prob.get("options", [])
            est_time = prob.get("estimated_time", "")
            difficulty = prob.get("difficulty", "")

            # 문제 번호 + 유형 + 난이도
            header_parts = [f"<b>{number}.</b> [{p_type}]"]
            if difficulty:
                header_parts.append(f" (난이도: {difficulty})")
            if est_time:
                header_parts.append(f" [예상 소요: {est_time}]")
            elements.append(Paragraph(
                _escape_xml("".join(header_parts)),
                self.styles["QuestionNumber"],
            ))

            # 문제 내용
            question_elements = _process_text_with_latex(question, self.styles)
            elements.extend(question_elements)

            # 객관식 보기
            if options:
                for opt in options:
                    elements.append(Paragraph(
                        _escape_xml(str(opt)),
                        self.styles["OptionText"],
                    ))

            # 보충 수준: 힌트 박스
            if level == "remedial":
                hint = prob.get("explanation", "")
                if hint:
                    # 힌트는 풀이 방향만 간략히
                    hint_short = hint[:80] + "..." if len(hint) > 80 else hint
                    elements.append(Paragraph(
                        f"💡 <b>힌트:</b> {_escape_xml(hint_short)}",
                        self.styles["HintBox"],
                    ))

            # 풀이 공간
            if p_type in ("서술형", "계산"):
                elements.append(Spacer(1, 25 * mm))
            else:
                elements.append(Spacer(1, 8 * mm))

        return elements

    def _build_answer_pages(self, problems: list, level: str) -> list:
        """답안지 페이지를 구성한다."""
        elements = []
        title = LEVEL_TITLES.get(level, "학습 자료")

        elements.append(PageBreak())
        elements.append(Paragraph(
            f"<b>{_escape_xml(title)} - 정답 및 해설</b>",
            self.styles["SectionHeader"],
        ))
        elements.append(Spacer(1, 5 * mm))

        for prob in problems:
            number = prob.get("number", "")
            answer = prob.get("answer", "")
            explanation = prob.get("explanation", "")
            p_type = prob.get("type", "")

            # 정답
            elements.append(Paragraph(
                f"<b>{_escape_xml(str(number))}번 정답:</b> {_escape_xml(str(answer))}",
                self.styles["AnswerHeader"],
            ))

            # 해설
            if explanation:
                elements.append(Paragraph(
                    f"<b>해설:</b> {_escape_xml(explanation)}",
                    self.styles["ExplanationText"],
                ))

            # 보충 수준: 관련 기본 개념 정리 표시
            if level == "remedial":
                elements.append(Paragraph(
                    f"<b>📖 풀이 포인트:</b> {_escape_xml(explanation[:120] if explanation else '')}",
                    self.styles["ExplanationText"],
                ))

            elements.append(Spacer(1, 3 * mm))

        return elements

    def build_pdf(
        self,
        level: str,
        problems_data: dict,
        subject: str,
        unit: str,
        output_path: str,
        class_name: str = "",
    ) -> str:
        """
        수준별 문제지 PDF를 생성한다.

        Args:
            level: "advanced" / "standard" / "remedial"
            problems_data: {"problems": [...], "level_summary": "..."}
            subject: 과목명
            unit: 단원명
            output_path: 저장 경로
            class_name: 학급명

        Returns:
            생성된 PDF 파일 경로
        """
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)

        problems = problems_data.get("problems", [])
        level_summary = problems_data.get("level_summary", "")

        if not problems:
            logger.warning(f"[{level}] 생성할 문제가 없습니다.")
            return ""

        def add_page_number(canvas, doc):
            canvas.saveState()
            if self.font_ready:
                canvas.setFont(FONT_NAME, 9)
            canvas.setFillColor(colors.HexColor("#999999"))
            page_num = canvas.getPageNumber()
            text = f"- {page_num} -"
            canvas.drawCentredString(PAGE_WIDTH / 2, 15 * mm, text)
            # 상단 라인
            level_color = LEVEL_COLORS.get(level, colors.grey)
            canvas.setStrokeColor(level_color)
            canvas.setLineWidth(2)
            canvas.line(20 * mm, PAGE_HEIGHT - 15 * mm,
                       PAGE_WIDTH - 20 * mm, PAGE_HEIGHT - 15 * mm)
            canvas.restoreState()

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            topMargin=20 * mm,
            bottomMargin=25 * mm,
            leftMargin=20 * mm,
            rightMargin=20 * mm,
        )

        elements = []
        elements.extend(self._build_cover_page(level, subject, unit, class_name))
        elements.extend(self._build_problem_pages(problems, level, level_summary))
        elements.extend(self._build_answer_pages(problems, level))

        doc.build(elements, onFirstPage=add_page_number, onLaterPages=add_page_number)
        logger.info(f"PDF 생성 완료: {output_path}")
        return output_path

    def build_all_pdfs(
        self,
        all_results: dict,
        subject: str,
        unit: str,
        output_dir: str = "output",
        class_name: str = "",
    ) -> dict:
        """
        모든 수준의 PDF를 생성한다.

        Returns:
            {level: filepath}
        """
        os.makedirs(output_dir, exist_ok=True)
        paths = {}
        level_filenames = {
            "advanced": "심화_문제지.pdf",
            "standard": "표준_문제지.pdf",
            "remedial": "보충_문제지.pdf",
        }

        for level, data in all_results.items():
            if not data or not data.get("problems"):
                continue
            filename = level_filenames.get(level, f"{level}_문제지.pdf")
            filepath = os.path.join(output_dir, filename)
            result = self.build_pdf(level, data, subject, unit, filepath, class_name)
            if result:
                paths[level] = result

        return paths
