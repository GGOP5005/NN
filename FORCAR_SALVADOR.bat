@echo off
title TECON SALVADOR - MODO VISUAL
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ROBO DE SALVADOR...
echo ===================================================
echo.

%PYTHON% scraper_salvador.py

echo.
pause