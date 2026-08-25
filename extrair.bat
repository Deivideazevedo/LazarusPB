@echo off
setlocal
title Lazarus IA - Extrair PBLs
set SCRIPTS=%~dp0scripts

echo ============================================
echo   Lazarus IA - Extrair codigo-fonte (.sr*)
echo ============================================
echo.

"%SCRIPTS%\python32\python.exe" "%SCRIPTS%\extrair.py" %*
if errorlevel 1 goto :falhou

echo.
echo Concluido! Fontes em:
echo   codigo_fonte\   (uma subpasta por PBL)
echo Log: logs\*.extracao.txt
echo.
pause
exit /b 0

:falhou
echo.
echo ERRO: extracao falhou. Veja as mensagens acima.
echo.
pause
exit /b 1
