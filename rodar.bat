@echo off
title Jogo de Imitacao de Poses - PDI UFMA
cd /d "%~dp0"
echo Iniciando o inicializador automatico do jogo...
python rodar.py %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo Ocorreu um erro ao executar. Pressione qualquer tecla para fechar.
    pause >nul
)
