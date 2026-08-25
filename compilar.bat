@echo off
setlocal
title Lazarus IA - Compilar PBLs
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Compilar PBLs (.pbl recriados)
echo ============================================
echo.
echo Lembrete: compile apenas depois de editar os
echo arquivos .sr* em codigo_fonte\.
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\compilar.py" %*
if errorlevel 1 goto :falhou

echo.
echo Concluido! .pbl recriados em:
echo   compilacao\   (um .pbl por PBL)
echo Log: logs\*.import.txt
echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: compilacao falhou. Veja os logs acima.
echo.
pause
exit /b 1
