@echo off
setlocal
title Lazarus IA - Compilar PATCH (somente alterados)
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Compilar PATCH (patch.pbl)
echo ============================================
echo.
echo Compara codigo_fonte\ com a baseline de
echo hashes.json e compila so os alterados.
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\compilar_patch.py" %*
if errorlevel 1 goto :falhou

echo.
echo Concluido! Patch em:
echo   compilacao\patch.pbl
echo Log: logs\patch.import.txt
echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: compilacao do patch falhou. Veja os logs acima.
echo.
pause
exit /b 1
