@echo off
rem Pass me the location of Python (e.g. c:\python22)

set PATH=%1;%PATH%
set PATH
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-
echo Commands available in twisted: twistd mktap manhole tapconvert ckeygen trial coil lore websetroot
echo -:- -:- -:- -:- -:--:- -:- -:- -:- -:--:- -:- -:- -:- -:-

rem  # The following scripts are not advertised for the following reasons
rem  #  conch - issues an exception when run with no arguments
rem  #  im, t-im - issue exceptions for missing gtk when run
rem  #  tap2deb - platform-specific
rem  #  tk* - no need; the ones that work have icons in the start menu