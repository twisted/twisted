"""
Use MingW to compile twisted_command.c and create EXE wrappers for every
Twisted command.
"""

import os, shutil, sys

thisDir = os.path.dirname(__file__)
binDir = os.path.join(thisDir, "..", "bin")
pyIncludeDir = os.path.join(sys.prefix, "include")
pyLibsDir = os.path.join(sys.prefix, "libs")
libName = "python" + sys.version[:3].replace('.', '')
buildDir = "twisted_cmds"
cmdName = "twisted_command"
cPath = os.path.join(thisDir, "%s.c" % (cmdName,))
rcPath = os.path.join(thisDir, "%s.rc" % (cmdName,))
exeName = "%s.exe" % (cmdName,)
oName = "%s.o" % (cmdName,)

if os.path.exists(exeName):
    os.unlink(exeName)

if os.path.exists(oName):
    os.unlink(oName)

os.system("gcc -c -mno-cygwin %s -I%s" % (cPath, pyIncludeDir))
os.system("windres %s %s_res.o" % (rcPath, cmdName))
os.system("gcc %s.o %s_res.o -L%s -lmsvcr71 -l%s -o %s" % (cmdName, cmdName, pyLibsDir, libName, exeName))

if not os.path.exists(exeName):
    print 'gcc produced no output file. exiting.'
    sys.exit(1)

def nameOK(s):
    for c in s:
        if not c.isalpha() and c != '-':
            return False
    return True

# gather twisted command names ignoring any junk files
cmdNames = []
for x in os.listdir(binDir):
    if not nameOK(x):
        continue

    if os.path.isdir(os.path.join(binDir, x)): 
        for y in os.listdir(os.path.join(binDir, x)):
            if os.path.isfile(os.path.join(binDir, x, y)) and nameOK(y):
                cmdNames.append(y)
    else:
        cmdNames.append(x)

if not os.path.exists(buildDir):
    os.mkdir(buildDir)

for cmd in cmdNames:
    shutil.copyfile(exeName, os.path.join(buildDir, cmd+'.exe'))

print "All EXEs created in 'twisted_cmds' directory!"

