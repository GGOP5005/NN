@echo off
title ROBO DE NAVIOS - TECON SUAPE
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ROBO DE NAVIOS...
echo ===================================================
echo.

%PYTHON% -c "from monitor_navios import iniciar_missao_navios; iniciar_missao_navios()"

echo.
pause