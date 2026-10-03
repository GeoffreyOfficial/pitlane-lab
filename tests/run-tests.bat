@echo off
rem Lance la suite de tests (Windows). Exemples : tests\run-tests.bat   |   tests\run-tests.bat -m static   |   tests\run-tests.bat --full
cd /d "%~dp0\.."
if not exist .venv-tests (
  python -m venv .venv-tests
  .venv-tests\Scripts\pip install -q -r tests\requirements.txt
  .venv-tests\Scripts\python -m playwright install chromium
)
if not exist tests\artifacts mkdir tests\artifacts
.venv-tests\Scripts\python -m pytest --html=tests\artifacts\rapport.html --self-contained-html %*
echo.
echo Rapport : tests\artifacts\rapport.html
