@echo off
echo PDF 생성기 exe 빌드 중...
pip install pyinstaller
pyinstaller --onefile --windowed --name "수준별학습자료생성기" ^
  --add-data "fonts;fonts" ^
  --add-data "config.json;." ^
  main.py
echo 빌드 완료! dist 폴더를 확인하세요.
pause
