#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils-launcher for Twisted projects.
"""

import sys, os, glob

subprojects = ['core', 'conch', 'lore', 'mail', 'names',
               'runner', 'web', 'words', 'news']


def runInDir(dir, f, *args, **kw):
    origdir = os.path.abspath('.')
    os.chdir(dir)
    try:
        return f(*args, **kw)
    finally:
        os.chdir(origdir)

def runSetup(project, args):
    dir = getProjDir(project)

    setupPy = os.path.join(dir, 'setup.py')
    if not os.path.exists(setupPy):
        sys.stderr.write("Error: No such project '%s'.\n" % (project,))
        sys.stderr.write(" (File '%s' not found)\n" % (setupPy,))
        sys.exit(1)

    result = runInDir(dir, os.spawnv,
                          os.P_WAIT, sys.executable,
                          [sys.executable, 'setup.py'] + args)
    if result != 0:
        sys.stderr.write("Error: Subprocess exited with result %d for project %s\n" %
                         (result, project))
        sys.exit(1)


def getProjDir(proj):
    globst = 'Twisted%s-*' % (proj != 'core'
                              and proj.capitalize() or '')
    gl = glob.glob(globst)
    assert len(gl) == 1, 'Wrong number of %s found!?' % proj
    dir = gl[0]
    return dir
        
def printProjectInfo(out=sys.stdout):
    out.write(
"""Twisted: The Framework Of Your Internet.
Usage: setup.py <project> <distutils args...>
       setup.py all <distutils args..>

E.g. setup.py all install
or   setup.py core --help

""")
    out.write("%-10s %-10s\n" % ("Project", "Version"))

    for project in subprojects:
        dir = getProjDir(project)
        ver = dir.split('-')[-1]
        out.write(" %-10s %-10s\n" % (project, ver))


def main(args):
    os.environ["PYTHONPATH"] = "." + os.pathsep + os.getenv("PYTHONPATH", "")
    if len(args) == 0 or args[0] in ('-h', '--help'):
        printProjectInfo()
        sys.exit(0)

    # if it's not a project name, it's a command name
    if args[0] not in ['all'] + subprojects:
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
