attrib /s -r
python setup.py build --compiler=mingw32
python setup.py bdist_wininst --install-script=twisted-postinstall.py
