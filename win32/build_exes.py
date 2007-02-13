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
cPath = os.path.join(thisDir, "twisted_command.c")
buildDir = "twisted_cmds"
exeName = "twisted_command.exe"
oName = "twisted_command.o"

if os.path.exists(exeName):
    os.unlink(exeName)

if os.path.exists(oName):
    os.unlink(oName)

os.system("gcc -mno-cygwin %s -I%s -L%s -lmsvcr71 -l%s -o %s" % (cPath, pyIncludeDir, pyLibsDir, libName, exeName))

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

