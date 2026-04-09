"""
수준별 개별화 학습 자료 자동 생성 시스템
메인 실행 파일 - Tkinter GUI (한글 UI, 탭 구조)
"""

import json
import logging
import os
import platform
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

# 프로젝트 모듈
from grade_analyzer import GradeAnalyzer, generate_sample_data
from ai_engine import AIEngine, SUBJECTS
from pdf_builder import PDFBuilder

# ── 로깅 설정 ──
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
log_file = os.path.join(LOG_DIR, time.strftime("%Y%m%d") + ".log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
SAMPLE_DATA_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "sample_data", "sample_scores.xlsx"
)


def load_config() -> dict:
    """설정 파일을 불러온다."""
    defaults = {
        "school_name": "",
        "teacher_name": "",
        "subject": "물리학",
        "default_unit": "",
        "advanced_percentile": 30,
        "remedial_percentile": 30,
        "problems_per_level": 10,
        "problem_types": ["객관식", "단답형", "서술형", "계산"],
        "output_dir": "output",
        "model": "claude-sonnet-4-20250514",
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            defaults.update(saved)
        except Exception as e:
            logger.warning(f"설정 파일 로드 실패: {e}")
    return defaults


def save_config(config: dict):
    """설정 파일을 저장한다."""
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


class Application(tk.Tk):
    """메인 애플리케이션 윈도우"""

    def __init__(self):
        super().__init__()
        self.title("수준별 개별화 학습 자료 자동 생성 시스템")
        self.geometry("900x700")
        self.minsize(800, 600)

        self.config_data = load_config()
        self.analyzer = GradeAnalyzer()
        self.ai_engine = None
        self.generated_results = {}
        self.generated_pdfs = {}

        # 샘플 데이터 자동 생성
        if not os.path.exists(SAMPLE_DATA_PATH):
            try:
                generate_sample_data(SAMPLE_DATA_PATH)
                logger.info("샘플 데이터 자동 생성 완료")
            except Exception as e:
                logger.warning(f"샘플 데이터 생성 실패: {e}")

        self._build_ui()

    def _build_ui(self):
        """전체 UI를 구성한다."""
        # 탭 노트북
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 탭 생성
        self.tab_api = ttk.Frame(self.notebook)
        self.tab_data = ttk.Frame(self.notebook)
        self.tab_generate = ttk.Frame(self.notebook)
        self.tab_pdf = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_api, text="  ① API 설정  ")
        self.notebook.add(self.tab_data, text="  ② 데이터 & 설정  ")
        self.notebook.add(self.tab_generate, text="  ③ 문제 생성  ")
        self.notebook.add(self.tab_pdf, text="  ④ PDF 출력  ")

        self._build_tab_api()
        self._build_tab_data()
        self._build_tab_generate()
        self._build_tab_pdf()

        # 상태바
        self.status_var = tk.StringVar(value="준비 완료")
        status_bar = ttk.Label(self, textvariable=self.status_var, relief=tk.SUNKEN,
                               anchor=tk.W, padding=(5, 2))
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    # ═══════════════════════════════════════════
    # 탭 1: API 설정
    # ═══════════════════════════════════════════
    def _build_tab_api(self):
        frame = ttk.LabelFrame(self.tab_api, text="Anthropic API 설정", padding=15)
        frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # API 키
        ttk.Label(frame, text="API 키:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(frame, textvariable=self.api_key_var, width=60, show="●")
        self.api_key_entry.grid(row=0, column=1, sticky=tk.W, padx=5, pady=5)

        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="키 표시", variable=self.show_key_var,
                        command=self._toggle_key_visibility).grid(row=0, column=2, padx=5)

        # 연결 테스트
        ttk.Button(frame, text="연결 테스트", command=self._test_connection).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.connection_status = ttk.Label(frame, text="")
        self.connection_status.grid(row=1, column=1, sticky=tk.E, padx=5)

        # 모델 선택
        ttk.Label(frame, text="모델:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.model_var = tk.StringVar(value=self.config_data.get("model", "claude-sonnet-4-20250514"))
        self.model_combo = ttk.Combobox(frame, textvariable=self.model_var, width=40, state="readonly")
        self.model_combo["values"] = [
            "claude-sonnet-4-20250514",
            "claude-haiku-4-5-20251001",
        ]
        self.model_combo.grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=3, column=0, columnspan=3, sticky=tk.EW, pady=15)

        # 학교명 / 교수명
        ttk.Label(frame, text="학교명:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.school_var = tk.StringVar(value=self.config_data.get("school_name", ""))
        ttk.Entry(frame, textvariable=self.school_var, width=40).grid(
            row=4, column=1, sticky=tk.W, padx=5, pady=5)

        ttk.Label(frame, text="출제자명:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.teacher_var = tk.StringVar(value=self.config_data.get("teacher_name", ""))
        ttk.Entry(frame, textvariable=self.teacher_var, width=40).grid(
            row=5, column=1, sticky=tk.W, padx=5, pady=5)

        # 저장 버튼
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=15)
        ttk.Button(btn_frame, text="설정 저장", command=self._save_settings).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="설정 불러오기", command=self._load_settings).pack(side=tk.LEFT, padx=5)

    def _toggle_key_visibility(self):
        self.api_key_entry.config(show="" if self.show_key_var.get() else "●")

    def _test_connection(self):
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("경고", "API 키를 입력하세요.")
            return
        self.connection_status.config(text="연결 테스트 중...", foreground="blue")
        self.update_idletasks()

        def _test():
            try:
                self.ai_engine = AIEngine(api_key, self.model_var.get())
                self.ai_engine.test_connection()
                self.after(0, lambda: self.connection_status.config(
                    text="✓ 연결 성공!", foreground="green"))
                self.after(0, lambda: self.status_var.set("API 연결 성공"))
            except Exception as e:
                self.after(0, lambda: self.connection_status.config(
                    text=f"✗ 연결 실패", foreground="red"))
                self.after(0, lambda: messagebox.showerror("연결 실패", str(e)))

        threading.Thread(target=_test, daemon=True).start()

    def _save_settings(self):
        self.config_data.update({
            "school_name": self.school_var.get(),
            "teacher_name": self.teacher_var.get(),
            "model": self.model_var.get(),
        })
        save_config(self.config_data)
        messagebox.showinfo("저장 완료", "설정이 저장되었습니다.")

    def _load_settings(self):
        self.config_data = load_config()
        self.school_var.set(self.config_data.get("school_name", ""))
        self.teacher_var.set(self.config_data.get("teacher_name", ""))
        self.model_var.set(self.config_data.get("model", "claude-sonnet-4-20250514"))
        messagebox.showinfo("불러오기 완료", "설정을 불러왔습니다.")

    # ═══════════════════════════════════════════
    # 탭 2: 데이터 & 설정
    # ═══════════════════════════════════════════
    def _build_tab_data(self):
        # 상단: 파일 불러오기
        file_frame = ttk.LabelFrame(self.tab_data, text="성적 파일 불러오기", padding=10)
        file_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

        btn_row = ttk.Frame(file_frame)
        btn_row.pack(fill=tk.X)
        ttk.Button(btn_row, text="파일 선택", command=self._load_grade_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text="샘플 데이터 사용", command=self._load_sample_data).pack(
            side=tk.LEFT, padx=5)
        self.file_label = ttk.Label(btn_row, text="파일을 선택하세요")
        self.file_label.pack(side=tk.LEFT, padx=10)

        # 컬럼 매핑
        map_frame = ttk.Frame(file_frame)
        map_frame.pack(fill=tk.X, pady=5)
        ttk.Label(map_frame, text="학생이름 컬럼:").pack(side=tk.LEFT, padx=5)
        self.name_col_var = tk.StringVar()
        self.name_col_combo = ttk.Combobox(map_frame, textvariable=self.name_col_var,
                                            width=15, state="readonly")
        self.name_col_combo.pack(side=tk.LEFT, padx=5)
        ttk.Label(map_frame, text="점수 컬럼:").pack(side=tk.LEFT, padx=5)
        self.score_col_var = tk.StringVar()
        self.score_col_combo = ttk.Combobox(map_frame, textvariable=self.score_col_var,
                                             width=15, state="readonly")
        self.score_col_combo.pack(side=tk.LEFT, padx=5)
        ttk.Button(map_frame, text="분류 실행", command=self._classify_students).pack(
            side=tk.LEFT, padx=10)

        # 수준 분류 기준
        criteria_frame = ttk.LabelFrame(self.tab_data, text="수준 분류 기준", padding=10)
        criteria_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(criteria_frame, text="상위 심화 (%)").grid(row=0, column=0, padx=5)
        self.adv_pct_var = tk.IntVar(value=self.config_data.get("advanced_percentile", 30))
        adv_scale = ttk.Scale(criteria_frame, from_=10, to=50, variable=self.adv_pct_var,
                              orient=tk.HORIZONTAL, length=150,
                              command=lambda v: self.adv_pct_label.config(text=f"{int(float(v))}%"))
        adv_scale.grid(row=0, column=1, padx=5)
        self.adv_pct_label = ttk.Label(criteria_frame, text=f"{self.adv_pct_var.get()}%")
        self.adv_pct_label.grid(row=0, column=2, padx=5)

        ttk.Label(criteria_frame, text="하위 보충 (%)").grid(row=0, column=3, padx=5)
        self.rem_pct_var = tk.IntVar(value=self.config_data.get("remedial_percentile", 30))
        rem_scale = ttk.Scale(criteria_frame, from_=10, to=50, variable=self.rem_pct_var,
                              orient=tk.HORIZONTAL, length=150,
                              command=lambda v: self.rem_pct_label.config(text=f"{int(float(v))}%"))
        rem_scale.grid(row=0, column=4, padx=5)
        self.rem_pct_label = ttk.Label(criteria_frame, text=f"{self.rem_pct_var.get()}%")
        self.rem_pct_label.grid(row=0, column=5, padx=5)

        # 과목/단원 설정
        subject_frame = ttk.LabelFrame(self.tab_data, text="과목/단원 설정", padding=10)
        subject_frame.pack(fill=tk.X, padx=15, pady=5)

        ttk.Label(subject_frame, text="과목:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.subject_var = tk.StringVar(value=self.config_data.get("subject", "물리학"))
        subject_combo = ttk.Combobox(subject_frame, textvariable=self.subject_var,
                                      width=20, state="readonly")
        subject_combo["values"] = SUBJECTS
        subject_combo.grid(row=0, column=1, padx=5, sticky=tk.W)

        ttk.Label(subject_frame, text="단원:").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.unit_var = tk.StringVar(value=self.config_data.get("default_unit", ""))
        ttk.Entry(subject_frame, textvariable=self.unit_var, width=30).grid(
            row=0, column=3, padx=5, sticky=tk.W)

        # 미리보기 테이블
        preview_frame = ttk.LabelFrame(self.tab_data, text="수준별 분류 결과 미리보기", padding=10)
        preview_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))

        columns = ("name", "score", "level")
        self.preview_tree = ttk.Treeview(preview_frame, columns=columns, show="headings",
                                          height=12)
        self.preview_tree.heading("name", text="학생이름")
        self.preview_tree.heading("score", text="점수")
        self.preview_tree.heading("level", text="수준")
        self.preview_tree.column("name", width=120)
        self.preview_tree.column("score", width=80, anchor=tk.CENTER)
        self.preview_tree.column("level", width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(preview_frame, orient=tk.VERTICAL,
                                   command=self.preview_tree.yview)
        self.preview_tree.configure(yscrollcommand=scrollbar.set)
        self.preview_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def _load_grade_file(self):
        filepath = filedialog.askopenfilename(
            title="성적 파일 선택",
            filetypes=[
                ("엑셀/CSV 파일", "*.xlsx *.xls *.csv"),
                ("엑셀 파일", "*.xlsx *.xls"),
                ("CSV 파일", "*.csv"),
                ("모든 파일", "*.*"),
            ],
        )
        if filepath:
            self._process_file(filepath)

    def _load_sample_data(self):
        if not os.path.exists(SAMPLE_DATA_PATH):
            generate_sample_data(SAMPLE_DATA_PATH)
        self._process_file(SAMPLE_DATA_PATH)

    def _process_file(self, filepath):
        try:
            self.analyzer.load_file(filepath)
            columns = self.analyzer.get_columns()
            self.name_col_combo["values"] = columns
            self.score_col_combo["values"] = columns
            # 자동 매핑 시도
            for col in columns:
                if "이름" in col or "name" in col.lower():
                    self.name_col_var.set(col)
                if "점수" in col or "score" in col.lower() or "성적" in col:
                    self.score_col_var.set(col)
            self.file_label.config(text=f"✓ {os.path.basename(filepath)} ({len(self.analyzer.df)}명)")
            self.status_var.set(f"파일 로드 완료: {os.path.basename(filepath)}")
        except Exception as e:
            messagebox.showerror("파일 오류", str(e))

    def _classify_students(self):
        name_col = self.name_col_var.get()
        score_col = self.score_col_var.get()
        if not name_col or not score_col:
            messagebox.showwarning("경고", "학생이름 컬럼과 점수 컬럼을 선택하세요.")
            return
        try:
            self.analyzer.advanced_pct = self.adv_pct_var.get()
            self.analyzer.remedial_pct = self.rem_pct_var.get()
            self.analyzer.set_column_mapping(name_col, score_col)
            self.analyzer.classify_students()

            # 테이블 업데이트
            for item in self.preview_tree.get_children():
                self.preview_tree.delete(item)

            for row in self.analyzer.get_classified_data():
                tag = row["level"]
                self.preview_tree.insert("", tk.END, values=(
                    row["name"], row["score"], row["level_kr"]
                ), tags=(tag,))

            self.preview_tree.tag_configure("advanced", foreground="#1565C0")
            self.preview_tree.tag_configure("standard", foreground="#F57F17")
            self.preview_tree.tag_configure("remedial", foreground="#2E7D32")

            stats = self.analyzer.get_level_stats()
            summary_parts = []
            for level, kr in [("advanced", "심화"), ("standard", "표준"), ("remedial", "보충")]:
                s = stats.get(level, {})
                summary_parts.append(f"{kr}: {s.get('count', 0)}명 (평균 {s.get('avg_score', 0)}점)")
            self.status_var.set("분류 완료 - " + " | ".join(summary_parts))

        except Exception as e:
            messagebox.showerror("분류 오류", str(e))

    # ═══════════════════════════════════════════
    # 탭 3: 문제 생성
    # ═══════════════════════════════════════════
    def _build_tab_generate(self):
        # 문제 유형 선택
        type_frame = ttk.LabelFrame(self.tab_generate, text="문제 유형 선택", padding=10)
        type_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

        self.type_vars = {}
        all_types = ["객관식", "단답형", "서술형", "계산"]
        for i, t in enumerate(all_types):
            var = tk.BooleanVar(value=True)
            ttk.Checkbutton(type_frame, text=t, variable=var).grid(row=0, column=i, padx=15)
            self.type_vars[t] = var

        # 수량 설정
        count_frame = ttk.LabelFrame(self.tab_generate, text="수준별 문제 수", padding=10)
        count_frame.pack(fill=tk.X, padx=15, pady=5)

        default_count = self.config_data.get("problems_per_level", 10)
        ttk.Label(count_frame, text="심화:").grid(row=0, column=0, padx=5)
        self.adv_count_var = tk.IntVar(value=default_count)
        ttk.Spinbox(count_frame, from_=1, to=30, textvariable=self.adv_count_var,
                    width=5).grid(row=0, column=1, padx=5)

        ttk.Label(count_frame, text="표준:").grid(row=0, column=2, padx=5)
        self.std_count_var = tk.IntVar(value=default_count)
        ttk.Spinbox(count_frame, from_=1, to=30, textvariable=self.std_count_var,
                    width=5).grid(row=0, column=3, padx=5)

        ttk.Label(count_frame, text="보충:").grid(row=0, column=4, padx=5)
        self.rem_count_var = tk.IntVar(value=default_count)
        ttk.Spinbox(count_frame, from_=1, to=30, textvariable=self.rem_count_var,
                    width=5).grid(row=0, column=5, padx=5)

        self.show_hints_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(count_frame, text="힌트 표시", variable=self.show_hints_var).grid(
            row=0, column=6, padx=15)

        # 생성 버튼
        btn_frame = ttk.Frame(self.tab_generate)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)
        self.generate_btn = ttk.Button(btn_frame, text="  ▶  문제 생성 시작  ",
                                        command=self._start_generation)
        self.generate_btn.pack(side=tk.LEFT, padx=5)
        self.cancel_btn = ttk.Button(btn_frame, text="취소", command=self._cancel_generation,
                                      state=tk.DISABLED)
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        # 프로그레스바
        progress_frame = ttk.LabelFrame(self.tab_generate, text="생성 진행 상황", padding=10)
        progress_frame.pack(fill=tk.X, padx=15, pady=5)

        self.progress_bars = {}
        self.progress_labels = {}
        for i, (level, kr) in enumerate([
            ("advanced", "심화"), ("standard", "표준"), ("remedial", "보충")
        ]):
            ttk.Label(progress_frame, text=f"{kr}:").grid(row=i, column=0, padx=5, sticky=tk.W)
            pb = ttk.Progressbar(progress_frame, length=400, mode="determinate")
            pb.grid(row=i, column=1, padx=5, pady=3)
            lbl = ttk.Label(progress_frame, text="대기 중")
            lbl.grid(row=i, column=2, padx=5)
            self.progress_bars[level] = pb
            self.progress_labels[level] = lbl

        # 실시간 로그
        log_frame = ttk.LabelFrame(self.tab_generate, text="생성 로그", padding=10)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))

        self.log_text = tk.Text(log_frame, height=10, state=tk.DISABLED, wrap=tk.WORD,
                                font=("Consolas", 9))
        log_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _append_log(self, message: str):
        """로그 텍스트에 메시지를 추가한다."""
        def _do():
            self.log_text.config(state=tk.NORMAL)
            timestamp = time.strftime("%H:%M:%S")
            self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.after(0, _do)

    def _update_progress(self, level: str, value: float):
        """프로그레스바를 업데이트한다."""
        def _do():
            if value < 0:
                self.progress_bars[level]["value"] = 0
                self.progress_labels[level].config(text="오류", foreground="red")
            elif value >= 1.0:
                self.progress_bars[level]["value"] = 100
                self.progress_labels[level].config(text="완료!", foreground="green")
            else:
                self.progress_bars[level]["value"] = value * 100
                self.progress_labels[level].config(text=f"{int(value * 100)}%", foreground="blue")
        self.after(0, _do)

    def _start_generation(self):
        # 유효성 검사
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showwarning("경고", "탭 ①에서 API 키를 입력하세요.")
            self.notebook.select(self.tab_api)
            return

        subject = self.subject_var.get()
        unit = self.unit_var.get().strip()
        if not unit:
            messagebox.showwarning("경고", "탭 ②에서 단원을 입력하세요.")
            self.notebook.select(self.tab_data)
            return

        selected_types = [t for t, v in self.type_vars.items() if v.get()]
        if not selected_types:
            messagebox.showwarning("경고", "최소 한 개 이상의 문제 유형을 선택하세요.")
            return

        # AI 엔진 초기화
        if self.ai_engine is None:
            self.ai_engine = AIEngine(api_key, self.model_var.get())
        else:
            self.ai_engine.api_key = api_key
            self.ai_engine.model = self.model_var.get()
            self.ai_engine.client = __import__("anthropic").Anthropic(api_key=api_key)

        # 수준별 설정 구성
        stats = self.analyzer.get_level_stats()
        levels_config = {
            "advanced": {
                "count": self.adv_count_var.get(),
                "avg_score": stats.get("advanced", {}).get("avg_score", 85),
            },
            "standard": {
                "count": self.std_count_var.get(),
                "avg_score": stats.get("standard", {}).get("avg_score", 60),
            },
            "remedial": {
                "count": self.rem_count_var.get(),
                "avg_score": stats.get("remedial", {}).get("avg_score", 35),
            },
        }

        # UI 상태 변경
        self.generate_btn.config(state=tk.DISABLED)
        self.cancel_btn.config(state=tk.NORMAL)
        for level in self.progress_bars:
            self.progress_bars[level]["value"] = 0
            self.progress_labels[level].config(text="대기 중", foreground="black")

        self._append_log("문제 생성을 시작합니다...")
        self._append_log(f"과목: {subject} / 단원: {unit}")
        self._append_log(f"문제 유형: {', '.join(selected_types)}")

        def _generate():
            try:
                results = self.ai_engine.generate_all_levels(
                    levels_config=levels_config,
                    subject=subject,
                    unit=unit,
                    problem_types=selected_types,
                    show_hints=self.show_hints_var.get(),
                    progress_callback=self._update_progress,
                    log_callback=self._append_log,
                )
                self.generated_results = results

                # 캐시 저장
                try:
                    cache_path = self.ai_engine.save_cache(results)
                    self._append_log(f"캐시 저장: {cache_path}")
                except Exception as e:
                    self._append_log(f"캐시 저장 실패: {e}")

                total = sum(len(r.get("problems", [])) for r in results.values())
                self._append_log(f"전체 완료! 총 {total}문항 생성됨")
                self.after(0, lambda: self.status_var.set(f"문제 생성 완료: 총 {total}문항"))
                self.after(0, lambda: messagebox.showinfo(
                    "생성 완료", f"총 {total}문항이 생성되었습니다.\n탭 ④에서 PDF를 저장하세요."))

            except Exception as e:
                self._append_log(f"오류 발생: {e}")
                self.after(0, lambda: messagebox.showerror("생성 오류", str(e)))
            finally:
                self.after(0, lambda: self.generate_btn.config(state=tk.NORMAL))
                self.after(0, lambda: self.cancel_btn.config(state=tk.DISABLED))

        threading.Thread(target=_generate, daemon=True).start()

    def _cancel_generation(self):
        if self.ai_engine:
            self.ai_engine.cancel()
            self._append_log("생성 취소 요청됨...")
            self.cancel_btn.config(state=tk.DISABLED)

    # ═══════════════════════════════════════════
    # 탭 4: PDF 출력
    # ═══════════════════════════════════════════
    def _build_tab_pdf(self):
        # 저장 경로 설정
        path_frame = ttk.LabelFrame(self.tab_pdf, text="저장 경로", padding=10)
        path_frame.pack(fill=tk.X, padx=15, pady=(15, 5))

        self.output_dir_var = tk.StringVar(
            value=os.path.join(os.path.dirname(os.path.abspath(__file__)), "output"))
        ttk.Entry(path_frame, textvariable=self.output_dir_var, width=60).pack(
            side=tk.LEFT, padx=5)
        ttk.Button(path_frame, text="폴더 선택", command=self._select_output_dir).pack(
            side=tk.LEFT, padx=5)

        # 버튼 영역
        btn_frame = ttk.LabelFrame(self.tab_pdf, text="PDF 생성", padding=15)
        btn_frame.pack(fill=tk.X, padx=15, pady=10)

        ttk.Button(btn_frame, text="심화 PDF 저장",
                   command=lambda: self._save_pdf("advanced")).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="표준 PDF 저장",
                   command=lambda: self._save_pdf("standard")).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="보충 PDF 저장",
                   command=lambda: self._save_pdf("remedial")).pack(side=tk.LEFT, padx=10)
        ttk.Button(btn_frame, text="  전체 저장  ",
                   command=self._save_all_pdfs).pack(side=tk.LEFT, padx=10)

        # 결과 표시
        result_frame = ttk.LabelFrame(self.tab_pdf, text="생성된 파일", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 15))

        self.pdf_result_text = tk.Text(result_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        self.pdf_result_text.pack(fill=tk.BOTH, expand=True)

        # 탐색기 열기 버튼
        ttk.Button(result_frame, text="출력 폴더 열기", command=self._open_output_folder).pack(
            pady=5)

    def _select_output_dir(self):
        d = filedialog.askdirectory(title="PDF 저장 폴더 선택")
        if d:
            self.output_dir_var.set(d)

    def _save_pdf(self, level: str):
        if not self.generated_results or level not in self.generated_results:
            messagebox.showwarning("경고", "먼저 탭 ③에서 문제를 생성하세요.")
            return

        data = self.generated_results[level]
        if not data or not data.get("problems"):
            messagebox.showwarning("경고", f"해당 수준의 생성된 문제가 없습니다.")
            return

        builder = PDFBuilder(self.school_var.get(), self.teacher_var.get())
        output_dir = self.output_dir_var.get()
        level_filenames = {
            "advanced": "심화_문제지.pdf",
            "standard": "표준_문제지.pdf",
            "remedial": "보충_문제지.pdf",
        }
        filepath = os.path.join(output_dir, level_filenames.get(level, f"{level}.pdf"))

        try:
            result = builder.build_pdf(
                level=level,
                problems_data=data,
                subject=self.subject_var.get(),
                unit=self.unit_var.get(),
                output_path=filepath,
            )
            if result:
                self.generated_pdfs[level] = result
                self._update_pdf_result()
                messagebox.showinfo("저장 완료", f"PDF 저장 완료:\n{result}")
        except Exception as e:
            messagebox.showerror("PDF 생성 오류", str(e))

    def _save_all_pdfs(self):
        if not self.generated_results:
            messagebox.showwarning("경고", "먼저 탭 ③에서 문제를 생성하세요.")
            return

        builder = PDFBuilder(self.school_var.get(), self.teacher_var.get())
        output_dir = self.output_dir_var.get()

        try:
            paths = builder.build_all_pdfs(
                all_results=self.generated_results,
                subject=self.subject_var.get(),
                unit=self.unit_var.get(),
                output_dir=output_dir,
            )
            self.generated_pdfs = paths
            self._update_pdf_result()

            if paths:
                msg = "PDF 저장 완료:\n" + "\n".join(paths.values())
                messagebox.showinfo("저장 완료", msg)
            else:
                messagebox.showwarning("경고", "저장된 PDF가 없습니다.")
        except Exception as e:
            messagebox.showerror("PDF 생성 오류", str(e))

    def _update_pdf_result(self):
        self.pdf_result_text.config(state=tk.NORMAL)
        self.pdf_result_text.delete("1.0", tk.END)
        level_names = {"advanced": "심화", "standard": "표준", "remedial": "보충"}
        for level, path in self.generated_pdfs.items():
            name = level_names.get(level, level)
            self.pdf_result_text.insert(tk.END, f"✓ [{name}] {path}\n")
        self.pdf_result_text.config(state=tk.DISABLED)

    def _open_output_folder(self):
        folder = self.output_dir_var.get()
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as e:
            messagebox.showinfo("폴더 경로", f"출력 폴더: {folder}")


def main():
    app = Application()
    app.mainloop()


if __name__ == "__main__":
    main()
