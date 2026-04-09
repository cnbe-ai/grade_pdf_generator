# 수준별 개별화 학습 자료 자동 생성 시스템

물리 교사를 위한 AI 기반 수준별 맞춤 문제지 자동 생성 도구입니다. 학급 성적 데이터(Excel/CSV)를 입력받아 Google Gemini AI가 학생 수준을 분석하고, 수준별 맞춤 문제를 생성한 뒤 인쇄 가능한 PDF로 출력합니다.

---

## 설치 방법

### 1. Python 설치
Python 3.10 이상이 필요합니다. [python.org](https://www.python.org/downloads/)에서 설치하세요.

### 2. 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 한글 폰트
프로그램 첫 실행 시 NanumGothic 폰트를 자동 다운로드합니다.
자동 다운로드가 실패하면 `fonts/` 폴더에 `NanumGothic.ttf` 파일을 직접 넣어주세요.

---

## 실행 방법

```bash
python main.py
```

프로그램이 실행되면 4개의 탭으로 구성된 GUI가 표시됩니다:

1. **① API 설정**: Google Gemini API 키 입력 및 연결 테스트
2. **② 데이터 & 설정**: 성적 파일 불러오기, 컬럼 매핑, 수준 분류
3. **③ 문제 생성**: 문제 유형/수량 설정 후 AI 문제 생성
4. **④ PDF 출력**: 수준별 PDF 저장 및 출력

---

## API 키 발급 방법 (무료)

1. [Google AI Studio](https://aistudio.google.com/)에 접속합니다
2. Google 계정으로 로그인합니다
3. 좌측 메뉴에서 **Get API key** 를 클릭합니다
4. **Create API key** 버튼을 클릭하여 키를 생성합니다
5. 생성된 키를 복사하여 프로그램의 ① API 설정 탭에 입력합니다

> API 키는 `AIza`로 시작합니다. 무료 등급(Free tier)으로도 충분히 사용 가능합니다.
> 키는 로컬에만 저장되며 Google AI 서버 외에는 전송되지 않습니다.

### 무료 사용량 (2024년 기준)
- **Gemini 3 Flash**: 분당 15회 요청, 일 1,500회 무료
- **Gemini 3.1 Flash Lite**: 분당 15회 요청, 일 1,500회 무료
- 수준별 10문항 기준 3회 호출이므로 하루 500세트 이상 생성 가능

---

## 성적 파일 형식

Excel(.xlsx) 또는 CSV(.csv) 파일을 지원합니다.

### 필수 컬럼
| 컬럼명 | 설명 | 예시 |
|--------|------|------|
| 학생이름 | 학생의 이름 | 김민준 |
| 점수 | 시험 점수 (숫자) | 85 |

> 컬럼명이 다른 경우 GUI에서 직접 매핑할 수 있습니다.

### 샘플 데이터
프로그램 첫 실행 시 `sample_data/sample_scores.xlsx` 파일이 자동 생성됩니다.
탭 ②에서 "샘플 데이터 사용" 버튼으로 바로 테스트할 수 있습니다.

---

## EXE 빌드 (Windows)

```batch
build_exe.bat
```

빌드 완료 후 `dist/` 폴더에 실행 파일이 생성됩니다.

---

## 자주 묻는 질문

### Q1. API 키를 입력했는데 연결이 안 됩니다.
- API 키가 `AIza`로 시작하는지 확인하세요.
- 인터넷 연결을 확인하세요.
- Google AI Studio에서 API 키가 활성 상태인지 확인하세요.

### Q2. 한글이 깨져서 표시됩니다.
- `fonts/` 폴더에 `NanumGothic.ttf` 파일이 있는지 확인하세요.
- 없다면 [네이버 나눔글꼴](https://hangeul.naver.com/font)에서 다운로드하여 넣어주세요.

### Q3. 문제 생성에 시간이 얼마나 걸리나요?
- 수준별 10문항 기준으로 각 수준당 약 20초~40초 정도 소요됩니다.
- 3개 수준이 병렬로 처리되므로 전체 약 30초~1분 내외입니다.

### Q4. 생성된 문제를 수정할 수 있나요?
- 생성 결과는 `output/cache/` 폴더에 JSON 파일로 자동 저장됩니다.
- JSON 파일을 직접 편집한 후 다시 PDF를 생성할 수 있습니다.

### Q5. 지원하는 과목은 무엇인가요?
- 통합과학, 물리학, 물질과 에너지, 전자기와 양자, 일반물리학을 지원합니다.
- 단원명은 자유롭게 입력할 수 있습니다.

---

## 프로젝트 구조

```
grade_pdf_generator/
├── main.py              # 메인 GUI (Tkinter)
├── ai_engine.py         # Gemini API 문제 생성
├── grade_analyzer.py    # 성적 분석 및 수준 분류
├── pdf_builder.py       # PDF 레이아웃 및 생성
├── config.json          # 설정 저장
├── requirements.txt     # Python 패키지
├── build_exe.bat        # Windows EXE 빌드
├── fonts/               # 한글 폰트
├── output/              # 생성된 PDF
├── sample_data/         # 샘플 성적 데이터
└── logs/                # 실행 로그
```
