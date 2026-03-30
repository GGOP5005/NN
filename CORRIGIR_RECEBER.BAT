@echo off
cd /d "%~dp0"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe
set PYTHONPATH=%~dp0

title ROBO BSOFT TMS - CODIGO GERENCIAL
echo ===================================================
echo   ROBO BSOFT TMS - TROCA DE CODIGO GERENCIAL
echo   Titulos a Receber: 08.002 -> Receita [Cliente]
echo ===================================================
echo.

%PYTHON% bsoft_codigo_gerencial.py

echo.
echo Codigo de saida: %ERRORLEVEL%
echo ===================================================
echo Operacao finalizada!
echo ===================================================
pause
