attrib /s -r
if not exist c:\python22\libs\libpython22.a goto :choke
python setup.py clean --all
python setup.py build --compiler=mingw32
python setup.py bdist_wininst --install-script=twisted_postinstall.py
@echo Press Ctrl+C to skip uploading
pause
scp dist/Twisted-*.exe shell.sf.net:/home/groups/t/tw/twisted/htdocs/
goto :done

:choke
rem libpython22.a must be present to build Twisted.  See 
rem http://sebsauvage.net/python/mingw.html

:done
