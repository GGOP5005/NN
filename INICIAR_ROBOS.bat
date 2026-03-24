@echo off
title CENTRAL DE COMANDO - LOGISTICA
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo     INICIANDO OS MOTORES DE AUTOMACAO...
echo ===================================================

echo [1/3] A ligar o Robo Extrator e Monitor de Pastas...
start "ROBO 1 - EXTRACAO" cmd /k "%PYTHON% main.py"

timeout /t 3 /nobreak > nul

echo [2/3] A ligar o Robo do Tecon Suape (Relogio)...
start "ROBO 2 - TECON" cmd /k "%PYTHON% main_monitor.py"

timeout /t 3 /nobreak > nul

echo [3/3] A ligar o Robo Monitor de Navios...
start "ROBO 3 - NAVIOS" cmd /k "%PYTHON% monitor_navios.py"

echo.
echo Tudo operacional! Tres janelas abertas.
timeout /t 5 > nul
exit