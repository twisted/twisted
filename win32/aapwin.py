import os.path, winreg

def getValueFromReg(key, valuename, default, hive=winreg.HKLM):
    """Pass valuename=None to get the (default) value."""
    try:
        key=winreg.Key(hive, key)
    except winreg.KeyNotFound:
        return default
    if valuename is None:
        return key.value
    try:
        return key.values[valuename].value
    except winreg.ValueNotFound:
        return default

def getPythonHomeForVersion(ver):
    """Return the home directory for a Python version specified as 'M.m'"""
    res = getValueFromReg(r'Software\Python\PythonCore\%s\InstallPath' %
                          ver, None, r'C:\pythonxx')
    if res == r'C:\pythonxx':
        res = getValueFromReg(r'Software\Python\PythonCore\%s\InstallPath' %
                              ver, None, r'C:\pythonxx', hive=winreg.HKCU)
    return res

def fileFromTemplate(filenametmpl, filenameout, dictionary):
    """Read filenametmpl, which is a template for filenameout with
    python %()s sequences.  Apply dictionary to it and write filenameout
    with the result.
    """
    tmplf = file(filenametmpl, 'r')
    tmpl = tmplf.read()
    tmplf.close()

    out = tmpl % dictionary
    outf = file(filenameout, 'w')
    outf.write(out)
    outf.close()

def lookupInnoHome():
    """Try either version 5 or version 4"""
    fallback = r'C:\Program Files\Inno Setup 5'
    regkey = r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall'
    _four = 'Inno Setup 4_is1'
    _five = 'Inno Setup 5_is1'
    _innohome = getValueFromReg(r'%s\%s' % (regkey, _five),
                                "Inno Setup: App Path",
                                None)
    if _innohome is None:
        _innohome = getValueFromReg(r'%s\%s' % (regkey, _four),
                                    "Inno Setup: App Path",
                                    None)
    if _innohome is None:
        return fallback
    else:
        return _innohome

innohome = lookupInnoHome()

pathdb = dict(innohome=innohome,
              iscc=os.path.join(innohome, "ISCC.exe"),
              python26=getPythonHomeForVersion('2.6'),
              python25=getPythonHomeForVersion('2.5'),
              python24=getPythonHomeForVersion('2.4'),
              )
