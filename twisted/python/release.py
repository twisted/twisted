"""
A release-automation toolkit.
"""

import sys, os, re

from twisted.python import failure, usage


#errors

class DirectoryExists(OSError):
    """Some directory exists when it shouldn't."""
    pass

class DirectoryDoesntExist(OSError):
    """Some directory doesn't exist when it should."""
    pass

class CommandFailed(OSError):
    pass


# utilities

def sh(command, null=True):#, sensitive=0):
    """
    I'll try to execute `command', and if `sensitive' is true, I'll
    ask before running it.  If the command returns something other
    than 0, I'll raise CommandFailed(command).
    """
    print "--$", command

    if True:#debug:# or sensitive:
        if raw_input("run ?? ").startswith('n'):
            return
    if null:
        command = "%s > /dev/null" % command
    if os.system(command) != 0:
        raise CommandFailed(command)


def replaceInFile(filename, oldstr, newstr):
    """
    I replace the text `oldstr' with `newstr' in `filename' using sed
    and mv.
    """
    os.rename(filename, filename+'.bak')
    f = open(filename+'.bak')
    d = f.read()
    f.close()
    d = d.replace(oldstr, newstr)
    f = open(filename + '.new', 'w')
    f.write(d)
    f.close()
    os.rename(filename+'.new', filename)

def runChdirSafe(f, *args, **kw):
    origdir = os.path.abspath('.')
    try:
        return f(*args, **kw)
    finally:
        os.chdir(origdir)


