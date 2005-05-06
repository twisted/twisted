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


innohome = getValueFromReg(r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 4_is1',
                          "Inno Setup: App Path",
                          r'C:\Program Files\Inno Setup 4')


pathdb = dict(innohome=innohome,
              iscc=os.path.join(innohome, "ISCC.exe"),
              python23=getPythonHomeForVersion('2.3'),
              python24=getPythonHomeForVersion('2.4'),
              )
