@echo off
setlocal
title Lazarus IA - Mapa de correspondencia entre PBLs (.sr*)
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Mapa de correspondencia
echo ============================================
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\origem.py" %*
if errorlevel 1 goto :falhou

echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: origem falhou. Veja as mensagens acima.
echo.
pause
exit /b 1
