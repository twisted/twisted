@echo off
rem Pass me the location of Python (e.g. c:\python22)

set PATH=%1;%PATH%
set PATH
set PATHEXT=%PATHEXT%;.py;.pyc;.pyo;.pyw
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
echo Commands available in twisted: twistd mktap manhole tapconvert ckeygen trial coil lore
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-

rem  # The following scripts are not advertised for the following reasons
rem  #  conch - issues an exception when run with no arguments
rem  #  im - issue exceptions for missing gtk when run
rem  #  tap2deb - platform-specific
rem  #  tk* - no need; the ones that work have icons in the start menu
