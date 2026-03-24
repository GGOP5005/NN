@echo off
title FORCAR EXECUCAO - TECON SUAPE
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ROBO DO TECON MANUALMENTE...
echo ===================================================
echo.

%PYTHON% -c "from main_monitor import executar_ciclo_completo; executar_ciclo_completo()"

echo.
echo ===================================================
echo Varredura manual finalizada!
echo ===================================================
pause