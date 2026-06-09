@echo off
echo Starting Flux 2 Klein Character Studio GUI...
cd /d "%~dp0\.."

set PYTHON=python
if exist "App\python_embeded\python.exe" (
    set PYTHON=App\python_embeded\python.exe
    echo Using embedded Python from App\python_embeded
)

echo Installing / updating UI dependencies (this may take a minute on first run)...
%PYTHON% -m pip install -r UI\requirements.txt --quiet --disable-pip-version-check

echo.
echo Resolving websockets version conflict (common in ComfyUI embedded env)...
%PYTHON% -m pip install "websockets>=13.0.0,<15.1.0" --force-reinstall --quiet

echo.
echo Launching Gradio interface...
%PYTHON% UI\flux_klein_character_studio.py

echo.
echo (If the window closed immediately, check the error above.)
pause