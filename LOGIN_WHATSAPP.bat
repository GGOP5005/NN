@echo off
title LOGIN WHATSAPP
cd /d "C:\ia_logistica_sheets"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

echo ===================================================
echo      ABRINDO LOGIN DO WHATSAPP...
echo ===================================================

%PYTHON% login_whatsapp.py

pause