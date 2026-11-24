@echo off
title Jogo de Imitacao de Poses - Webcam Local (PDI UFMA)
cd /d "%~dp0"
echo ========================================================
echo Iniciando jogo utilizando a webcam integrada do notebook...
echo ========================================================
python rodar.py 0
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao executar. Pressione qualquer tecla para fechar.
    pause >nul
)
