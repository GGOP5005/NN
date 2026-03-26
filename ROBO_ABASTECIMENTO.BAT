@echo off
cd /d "%~dp0"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

title ROBO ABASTECIMENTO BSOFT

if "%1"=="AGORA" (
    echo ============================================
    echo   EXECUTANDO CICLO AGORA ^(TESTE^)
    echo ============================================
    %PYTHON% robo_abastecimento.py --agora
) else (
    echo ============================================
    echo   ROBO ABASTECIMENTO - AGENDADOR
    echo   Execucoes: 08:00 e 20:00
    echo ============================================
    %PYTHON% robo_abastecimento.py
)

echo.
pause