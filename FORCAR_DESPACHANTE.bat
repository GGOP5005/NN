@echo off
title DESPACHANTE WHATSAPP - PROJETO 5
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ROBO DO WHATSAPP...
echo ===================================================
echo.

%PYTHON% despachante_whatsapp.py

echo.
pause