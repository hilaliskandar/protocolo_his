@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul
title Protocolo HIS - Inicializacao completa

rem ============================================================
rem Configuracao do ambiente local
rem Ajuste os caminhos abaixo caso a instalacao seja diferente.
rem ============================================================
set "PYTHON=C:\Users\USER\.conda\envs\protocolo-his\python.exe"
set "PG_BIN=C:\Program Files\PostgreSQL\17\bin"
set "PG_DATA=F:\ale_2_0\postgres_his_17\data"
set "PG_LOG=F:\ale_2_0\postgres_his_17\postgresql.log"
set "PROJECT_DIR=F:\ale_2_0\protocolo_his_local"
set "PG_HOST=127.0.0.1"
set "PG_PORT=55432"
set "PG_DATABASE=protocolo_his"
set "DJANGO_HOST=127.0.0.1"
set "DJANGO_PORT=8000"
set "MAX_TENTATIVAS=30"

echo.
echo ============================================================
echo            PROTOCOLO HIS - INICIALIZACAO
echo ============================================================
echo.

if not exist "%PYTHON%" (
    echo [ERRO] Python do ambiente Conda nao encontrado:
    echo        %PYTHON%
    goto :falha
)

if not exist "%PG_BIN%\pg_ctl.exe" (
    echo [ERRO] pg_ctl.exe nao encontrado:
    echo        %PG_BIN%\pg_ctl.exe
    goto :falha
)

if not exist "%PG_BIN%\pg_isready.exe" (
    echo [ERRO] pg_isready.exe nao encontrado:
    echo        %PG_BIN%\pg_isready.exe
    goto :falha
)

if not exist "%PG_DATA%\PG_VERSION" (
    echo [ERRO] Cluster PostgreSQL nao encontrado:
    echo        %PG_DATA%
    goto :falha
)

if not exist "%PROJECT_DIR%\manage.py" (
    echo [ERRO] Projeto Django nao encontrado:
    echo        %PROJECT_DIR%\manage.py
    goto :falha
)

echo [1/4] Verificando PostgreSQL...
"%PG_BIN%\pg_ctl.exe" status -D "%PG_DATA%" >nul 2>&1

if errorlevel 1 (
    echo       PostgreSQL parado. Iniciando cluster na porta %PG_PORT%...
    "%PG_BIN%\pg_ctl.exe" start -D "%PG_DATA%" -l "%PG_LOG%" -o "-p %PG_PORT%"
    if errorlevel 1 (
        echo [ERRO] Nao foi possivel iniciar o PostgreSQL.
        echo        Consulte o log: %PG_LOG%
        goto :falha
    )
) else (
    echo       PostgreSQL ja esta em execucao.
)

echo [2/4] Aguardando o banco aceitar conexoes...
set /a TENTATIVA=0

:aguardar_postgres
set /a TENTATIVA+=1
"%PG_BIN%\pg_isready.exe" -h "%PG_HOST%" -p "%PG_PORT%" -d "%PG_DATABASE%" >nul 2>&1

if not errorlevel 1 (
    echo       PostgreSQL disponivel em %PG_HOST%:%PG_PORT%.
    goto :postgres_pronto
)

if !TENTATIVA! GEQ %MAX_TENTATIVAS% (
    echo [ERRO] PostgreSQL nao ficou disponivel apos %MAX_TENTATIVAS% segundos.
    echo        Consulte o log: %PG_LOG%
    goto :falha
)

timeout /t 1 /nobreak >nul
goto :aguardar_postgres

:postgres_pronto
echo [3/4] Verificando a aplicacao Django...
pushd "%PROJECT_DIR%"

"%PYTHON%" manage.py check
if errorlevel 1 (
    popd
    echo [ERRO] O comando manage.py check encontrou problemas.
    goto :falha
)

echo [4/4] Iniciando o servidor Django...
echo.
echo       Aplicacao: http://%DJANGO_HOST%:%DJANGO_PORT%/
echo       Admin:     http://%DJANGO_HOST%:%DJANGO_PORT%/admin/
echo.
echo       Pressione CTRL+C para encerrar o servidor Django.
echo       O PostgreSQL permanecera ativo.
echo.

start "" cmd /c "timeout /t 3 /nobreak >nul && start \"\" http://%DJANGO_HOST%:%DJANGO_PORT%/"
"%PYTHON%" manage.py runserver %DJANGO_HOST%:%DJANGO_PORT%

set "DJANGO_EXIT=%ERRORLEVEL%"
popd

if not "%DJANGO_EXIT%"=="0" (
    echo.
    echo [AVISO] O servidor Django foi encerrado com codigo %DJANGO_EXIT%.
)

goto :fim

:falha
echo.
echo A inicializacao nao foi concluida.
echo.
pause
exit /b 1

:fim
echo.
echo Servidor Django encerrado.
echo O PostgreSQL continua em execucao na porta %PG_PORT%.
echo.
pause
endlocal
