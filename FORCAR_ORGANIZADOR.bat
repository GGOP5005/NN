@echo off
title ORGANIZADOR DE PASTAS - NORTE NORDESTE
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ACIONANDO O ORGANIZADOR DE PASTAS...
echo ===================================================
echo.

%PYTHON% organizador_meses.py

echo.
pause