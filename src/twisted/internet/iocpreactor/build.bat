@echo off
set args=-c mingw

if %1.==. goto build

if "%1" == "vs" (
    set args=
)

:build
del iocpsupport\iocpsupport.c iocpsupport.pyd
del /f /s /q build
python setup.py build_ext -i %args%

