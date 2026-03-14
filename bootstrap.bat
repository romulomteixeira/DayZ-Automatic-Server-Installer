set LOG=logs\bootstrap_%date:~-4%-%date:~3,2%-%date:~0,2%_%time:~0,2%%time:~3,2%.log

echo Iniciando bootstrap > %LOG%

python core\install_server.py >> %LOG% 2>&1
python core\install_mods.py >> %LOG% 2>&1

@echo off
title DayZ Automatic Server Installer
color 0A

echo =========================================
echo  DayZ Automatic Server Installer
echo =========================================

:: ---------------------------------------
:: CRIAR ESTRUTURA
:: ---------------------------------------

if not exist steamcmd mkdir steamcmd
if not exist servers mkdir servers
if not exist servers\server1 mkdir servers\server1
if not exist config mkdir config
if not exist web mkdir web
if not exist web\templates mkdir web\templates

:: ---------------------------------------
:: BAIXAR STEAMCMD
:: ---------------------------------------

if not exist steamcmd\steamcmd.exe (

echo.
echo Baixando SteamCMD...

powershell -Command ^
"$ProgressPreference = 'Continue'; Invoke-WebRequest https://steamcdn-a.akamaihd.net/client/installer/steamcmd.zip -OutFile steamcmd.zip"

echo Extraindo SteamCMD...

powershell -Command ^
"Expand-Archive steamcmd.zip steamcmd -Force"

del steamcmd.zip

)

echo SteamCMD pronto.

:: ---------------------------------------
:: DEFINIR CAMINHOS ABSOLUTOS
:: ---------------------------------------

set ROOT=%cd%
set SERVER_DIR=%ROOT%\servers\server1

if not exist "%SERVER_DIR%" (
 echo Criando pasta do servidor...
 mkdir "%SERVER_DIR%"
)

echo.
echo Instalando servidor DayZ usando credenciais do steam.json...

cd core
python install_server.py
cd ..

if not exist servers\server1\DayZServer_x64.exe (
    echo.
    echo ERRO: instalacao do servidor falhou
    echo Verifique logs\install_server.log
    pause
    exit
)

:: ---------------------------------------
:: CRIAR CONFIG
:: ---------------------------------------

if not exist servers\server1\serverDZ.cfg (

echo Criando serverDZ.cfg...

(
echo hostname = "DayZ Auto Server";
echo password = "";
echo passwordAdmin = "admin123";
echo maxPlayers = 40;
echo verifySignatures = 2;
echo disableVoN = 0;
echo vonCodecQuality = 20;
echo timeAcceleration = 6;
echo timePersistence = 1;
echo guaranteedUpdates = 1;
echo BattlEye = 1;
) > servers\server1\serverDZ.cfg

)

:: ---------------------------------------
:: LISTA DE MODS
:: ---------------------------------------

if not exist config\mods.json (

(
echo {
echo "mods":[
echo "1564026768",
echo "1559212036",
echo "1828439124"
echo ]
echo }
) > config\mods.json

)

:: ---------------------------------------
:: INSTALAR MODS
:: ---------------------------------------

echo.
echo Instalando mods...

python core\install_mods.py

if %ERRORLEVEL% NEQ 0 (
 echo ERRO na instalacao de mods
 pause
 exit
)

:: ---------------------------------------
:: INSTALAR MAPA CHIEMSEE
:: ---------------------------------------

echo.
echo Instalando mapa Chiemsee...

steamcmd\steamcmd.exe ^
+login anonymous ^
+workshop_download_item 221100 1940928446 ^
+quit

echo Mapa instalado.

:: ---------------------------------------
:: INSTALAR DEPENDENCIAS PYTHON
:: ---------------------------------------

echo flask>requirements.txt
echo psutil>>requirements.txt

python -m pip install -r requirements.txt

:: ---------------------------------------
:: CRIAR PAINEL WEB
:: ---------------------------------------

echo Criando painel web...

(
echo from flask import Flask,render_template
echo import psutil
echo app=Flask(__name__)
echo @app.route("/")
echo def index():
echo ^ cpu=psutil.cpu_percent()
echo ^ ram=psutil.virtual_memory().percent
echo ^ return render_template("dashboard.html",cpu=cpu,ram=ram)
echo app.run(port=8080)
) > web\panel.py

(
echo ^<h2^>DayZ Server Panel^</h2^>
echo CPU: {{cpu}}%%
echo ^<br^>
echo RAM: {{ram}}%%
) > web\templates\dashboard.html

:: ---------------------------------------
:: INICIAR PAINEL
:: ---------------------------------------

echo.
echo Iniciando painel...

start cmd /k "cd web && python panel.py"

:: ---------------------------------------
:: INICIAR SERVIDOR
:: ---------------------------------------

echo.
echo Iniciando servidor DayZ...

start servers\server1\DayZServer_x64.exe ^
-config=serverDZ.cfg ^
-port=2302 ^
-profiles=profiles ^
-dologs ^
-adminlog

echo.
echo =========================================
echo  Servidor pronto
echo =========================================
echo.
echo Painel:
echo http://localhost:8080
echo.

pause