attrib /s -r
python setup.py clean --all
python setup.py build --compiler=mingw32
python setup.py bdist_wininst --install-script=twisted_postinstall.py
@echo Press Ctrl+C to skip uploading
pause
scp dist/Twisted-*.exe shell.sf.net:/home/groups/t/tw/twisted/htdocs/
