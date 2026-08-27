@echo off
setlocal
title Lazarus IA - Analisar dependencias (.sr*)
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Analisar dependencias
echo ============================================
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\analise.py" %*
if errorlevel 1 goto :falhou

echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: analise falhou. Veja as mensagens acima.
echo.
pause
exit /b 1
