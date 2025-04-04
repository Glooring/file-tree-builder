@echo off
setlocal enabledelayedexpansion

:: ========================================
::  CONFIGURATION
:: ========================================
set APP_NAME=FileTreeBuilder
set VERSION=v1.0.0
set SRC_DIR=src
set OUT_EXE=%APP_NAME%.exe
set RELEASE_DIR=file-tree-builder-%VERSION%
set BIN_DIR=%RELEASE_DIR%\bin

:: Path to MSYS2 MinGW installation
set MINGW_BIN=D:\Apps\msys64\mingw64\bin
set INCLUDE_DIR=D:\Apps\msys64\mingw64\include
set LIB_DIR=D:\Apps\msys64\mingw64\lib

:: DLLs required by MinGW runtime
set DLLS=libfltk-1.4.dll libgcc_s_seh-1.dll libstdc++-6.dll libwinpthread-1.dll

echo.
echo =====================================
echo  Building: %APP_NAME% (FLTK + C++)
echo =====================================

:: ========================================
::  PREPARE RELEASE FOLDER
:: ========================================
if exist %RELEASE_DIR% rmdir /s /q %RELEASE_DIR%
mkdir %RELEASE_DIR%
mkdir %BIN_DIR%

:: ========================================
::  COMPILATION (output directly into release folder)
:: ========================================
g++ %SRC_DIR%\main.cpp %SRC_DIR%\gui.cpp %SRC_DIR%\file_tree.cpp ^
    -o %RELEASE_DIR%\%OUT_EXE% ^
    -I%SRC_DIR% ^
    -I"%INCLUDE_DIR%" -L"%LIB_DIR%" ^
    -std=c++17 -pthread -O2 -mwindows -lfltk -lole32 -luuid -lcomctl32 -lws2_32 -lgdi32 -lshlwapi

if errorlevel 1 (
    echo.
    echo [ERROR] Compilation FAILED!
    pause
    exit /b 1
)

echo.
echo [OK]    Compilation successful: %OUT_EXE% → %RELEASE_DIR%\

:: ========================================
::  COPY RUNTIME DLLs (next to .exe)
:: ========================================
for %%f in (%DLLS%) do (
    if exist "%MINGW_BIN%\%%f" (
        copy "%MINGW_BIN%\%%f" %RELEASE_DIR%\ >nul
        echo [OK]    Copied: %%f
    ) else (
        echo [WARN]  DLL not found: %%f
    )
)

echo.
echo [DONE] Release package is ready:
echo        %RELEASE_DIR%\
echo        ^|-- %OUT_EXE% (launch this file)
echo        ^|-- (runtime DLLs)
echo        ^|-- bin\
echo.
pause
endlocal
