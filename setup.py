#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils-launcher for Twisted projects.
"""

import sys, os, os.path

subprojects = ('core', 'conch', 'flow', 'lore', 'mail', 'names', 'pair',
               'runner', 'web', 'words', 'xish')

specialPaths = {'core': 'twisted/topfiles/setup.py'}
specialModules = {'core': 'twisted'}

def namedModule(name):
    """Return a module given its name."""
    topLevel = __import__(name)
    packages = name.split(".")[1:]
    m = topLevel
    for p in packages:
        m = getattr(m, p)
    return m

def firstLine(doc):
    for line in doc.splitlines():
        line = line.strip()
        if line:
            return line

    return ""

def runSetup(project, args):
    setupPy = specialPaths.get(project,
                   os.path.join('twisted', project, 'topfiles', 'setup.py'))

    if not os.path.exists(setupPy):
        sys.stderr.write("Error: No such project '%s'.\n" % (project,))
        sys.stderr.write(" (File '%s' not found)\n" % (setupPy,))
        sys.exit(1)

    result = os.spawnv(os.P_WAIT, sys.executable,
                   [sys.executable, setupPy] + args)
    if result != 0:
        sys.stderr.write("Error: Subprocess exited with result %d for project %s\n" %
                         (result, project))
        sys.exit(1)

def printProjectInfo(out=sys.stdout):
    out.write(
"""Twisted: The Framework Of Your Internet.
Usage: setup.py <project> <distutils args...>
       setup.py all <distutils args..>

E.g. setup.py all install
or   setup.py core --help

""")
    out.write(" %-10s %-10s %s\n" % ("Project", "Version", "Description"))
    
    for project in subprojects:
        try:
            mod = namedModule(specialModules.get(project, 'twisted.'+project))
        except (AttributeError, ImportError):
            out.write(" %-10s **unable to import**\n" % (project,))
        else:
            out.write(" %-10s %-10s %s\n" %
                      (project, mod.__version__, firstLine(mod.__doc__)))
        

def main(args):
    os.putenv("PYTHONPATH", "."+os.pathsep+os.getenv("PYTHONPATH", ""))
    if len(args) == 0 or args[0] in ('-h', '--help'):
        printProjectInfo()
        sys.exit(0)
        
    # special case common options
    if args[0] in ('install','build'):
        project = 'all'
    else:
        project = args[0]
        args = args[1:]
    
    if project == 'all':
        for project in subprojects:
            runSetup(project, args)
    else:
        runSetup(project, args)
        
if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)

    
