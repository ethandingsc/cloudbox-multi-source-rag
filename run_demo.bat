@echo off
rem CloudBox Support Assistant — one-click demo launcher (Step 5.3).
rem Switches to the project root (works from any folder), activates the
rem existing conda env `cloudbox-rag` and starts the Streamlit app.
rem No API keys here — the pipeline loads them from the project-root
rem .env (gitignored; see .env.example for the variable names).
cd /d "%~dp0"

call conda activate cloudbox-rag
if not errorlevel 1 goto :run

rem conda activate failed (conda not on PATH / not initialized in this
rem window) — fall back to the env's Python directly, at the default
rem per-user Anaconda location (no hard-coded username).
set "PY=%USERPROFILE%\anaconda3\envs\cloudbox-rag\python.exe"
if exist "%PY%" goto :run_direct

echo Failed to find the conda environment `cloudbox-rag`.
echo Open an Anaconda Prompt in this folder and run:
echo     conda activate cloudbox-rag
echo     python -m streamlit run app.py
pause
exit /b 1

:run
python -m streamlit run app.py
goto :end

:run_direct
"%PY%" -m streamlit run app.py

:end
rem Keep this window open if Streamlit exits or errors.
pause
