# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Utilities for dealing with processes.

@stability: Unstable
"""

import os, sys

from twisted.internet import reactor
from twisted.python.compat import sets

def which(name, flags=os.X_OK):
    """Search PATH for executable files with the given name.
    
    @type name: C{str}
    @param name: The name for which to search.
    
    @type flags: C{int}
    @param flags: Arguments to L{os.access}.
    
    @rtype: C{list}
    @param: A list of the full paths to files found, in the
    order in which they were found.
    """
    result = []
    exts = filter(None, os.environ.get('PATHEXT', '').split(os.pathsep))
    for p in os.environ['PATH'].split(os.pathsep):
        p = os.path.join(p, name)
        if os.access(p, flags):
            result.append(p)
        for e in exts:
            pext = p + e
            if os.access(pext, flags):
                result.append(pext)
    return result



def spawnProcess(processProtocol, executable, args=(), env={},
                 path=None, uid=None, gid=None, usePTY=0,
                 packages=()):
    """Launch a process with a particular Python environment.
 
    All arguments as to reactor.spawnProcess(), except for the
    addition of an optional packages iterable.  This should be
    of strings naming packages the subprocess is to be able to
    import.
    """
 
    env = env.copy()
 
    pythonpath = []
    for pkg in packages:
        p = os.path.split(imp.find_module(pkg)[1])[0]
        if p.startswith(os.path.join(sys.prefix, 'lib')):
            continue
        pythonpath.append(p)
    pythonpath = list(sets.Set(pythonpath))
    pythonpath.extend(env.get('PYTHONPATH', '').split(os.pathsep))
    env['PYTHONPATH'] = os.pathsep.join(pythonpath)
 
    return reactor.spawnProcess(processProtocol, executable, args,
                                env, path, uid, gid, usePTY)
 
def spawnPythonProcess(processProtocol, args=(), env={},
                       path=None, uid=None, gid=None, usePTY=0,
                       packages=()):
    """Launch a Python process
 
    All arguments as to spawnProcess(), except the executable
    argument is omitted.
    """
    return spawnProcess(processProtocol, sys.executable,
                        args, env, path, uid, gid, usePTY,
                        packages)
