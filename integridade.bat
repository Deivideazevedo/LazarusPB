@echo off
setlocal
title Lazarus IA - Integridade de Fontes (CP1252 / Acentos)
set SCRIPTS=%~dp0scripts

echo ====================================================
echo   Lazarus IA - Integridade de Fontes (.sr*)
echo ====================================================
echo.
echo [Dicas de uso]
echo   Normal / Correcao : integridade [pbl ou arquivo]
echo   Somente Leitura   : integridade -v ou --verificar [pbl ou arquivo]
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\integridade_fontes.py" %*
if errorlevel 1 goto :pendente

echo.
pause
exit /b 0

:pendente
echo.
echo Operacao cancelada ou pendencias detectadas.
echo.
pause
exit /b 1
