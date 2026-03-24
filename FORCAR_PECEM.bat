@echo off
title PORTO DO PECEM - GERADOR DE TAXAS
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ROBO DO PECEM...
echo ===================================================
echo.

%PYTHON% scraper_pecem.py

echo.
pause