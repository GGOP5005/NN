@echo off
cd /d "%~dp0"
set PYTHON=C:\Users\supor\AppData\Local\Programs\Python\Python312\python.exe

title ROBO BSOFT TMS - TITULOS A PAGAR
echo ===================================================
echo   ROBO BSOFT TMS - TITULOS A PAGAR
echo   Codigos: 09.007.005 e 09.007.006
echo ===================================================
echo.

echo Verificando Python...
%PYTHON% --version
echo.

echo Iniciando robo...
%PYTHON% -u bsoft_titulos_pagar.py

echo.
echo Codigo de saida: %ERRORLEVEL%
echo ===================================================
pause
