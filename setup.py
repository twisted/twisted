#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils-launcher for Twisted projects.
"""

import sys, os, glob

sumoSubprojects = ['core', 'conch', 'lore', 'mail', 'names',
                   'runner', 'web', 'words', 'news']

specialPaths = {'core': 'twisted/topfiles/setup.py'}


def runInDir(dir, f, *args, **kw):
    """ 
    Run a function after chdiring to a directory, and chdir back to
    the original directory afterwards, even if the function fails.
    """
    origdir = os.path.abspath('.')
    os.chdir(dir)
    try:
        return f(*args, **kw)
    finally:
        os.chdir(origdir)


def getSumoProjDir(proj):
    globst = 'Twisted%s-*' % proj.capitalize()
    gl = glob.glob(globst)
    assert len(gl) == 1, 'Wrong number of %s found!?' % proj
    dir = gl[0]
    return dir


def findSetupPy(project):
    """
    Try to find a setup.py file, and quit the process if none is found.
    @returns: tuple of (setup.py path,  sumoMode), where sumoMode is a boolean.
    """
    tried = []

    setupPy = specialPaths.get(project)
    tried.append(setupPy)
    if setupPy and os.path.exists(setupPy):
        return (setupPy, False)

    setupPy = os.path.join('twisted', project, 'topfiles', 'setup.py')
    tried.append(setupPy)
    if os.path.exists(setupPy):
        return (setupPy, False)

    setupPy = os.path.join(getSumoProjDir(project), 'setup.py')
    tried.append(setupPy)
    if os.path.exists(setupPy):
        return (setupPy, True)

    sys.stderr.write("Error: No such project '%s'.\n" % (project,))
    sys.stderr.write(" (%s not found)\n" % (tried,))
    sys.exit(1)

def runSetup(project, args):
    setupPy, sumoMode = findSetupPy(project)

    # Packaged setup.py files want to be run in the root directory of
    # their source, whereas out of SVN they should be run from the
    # root directory of the entire tree.
    if sumoMode:
        result = runInDir(os.path.dirname(setupPy), os.spawnv,
                          os.P_WAIT, sys.executable,
                          [sys.executable, 'setup.py'] + args)
    else:
        result = os.spawnv(os.P_WAIT, sys.executable,
                           [sys.executable, setupPy] + args)

    if result != 0:
        sys.stderr.write(
            "Error: Subprocess exited with result %d for project %s\n" %
            (result, project))
        sys.exit(1)


def main(args):
    os.environ["PYTHONPATH"] = "." + os.pathsep + os.getenv("PYTHONPATH", "")
    if len(args) == 0 or args[0] in ('-h', '--help'):
        sys.stdout.write(
"""Twisted: The Framework Of Your Internet.
Usage: setup.py <distutils args..>
""")
        runSetup('core', ['-h'])
        sys.exit(0)

    for project in sumoSubprojects:
        runSetup(project, args)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
