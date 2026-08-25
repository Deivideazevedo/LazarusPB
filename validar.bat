@echo off
setlocal
title Lazarus IA - Validar round-trip
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Validar PBLs recriados
echo ============================================
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\validar.py" %*
if errorlevel 1 goto :falhou

echo.
echo Concluido! Logs em:
echo   logs\*.validacao.txt
echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: validacao apontou divergencias. Veja os logs acima.
echo.
pause
exit /b 1
