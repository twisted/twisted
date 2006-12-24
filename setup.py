#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Distutils-launcher for Twisted projects.

This is a script which emulates a distutils-style setup.py, by delegating its
invocation arguments to actual distutils setup.py scripts for each Twisted
subproject in turn.

It locates other setup.py scripts by detecting whether it is run in a 'sumo'
configuration, which is the structure of the released tarballs, or a 'non-sumo'
(development) configuration, which is the structure of the SVN repository.
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
    """
    Return the existing directory which contains the specified
    subproject. If no applicable directory is found, None is returned
    (which may be because we are not running from a Sumo tarball). If
    more than one appropriate directory is found, an AssertionError is
    raised.
    """
    globst = 'Twisted%s-*' % proj.capitalize()
    gl = glob.glob(globst)
    assert not len(gl) > 1, 'Wrong number of %s directories found!?' % (proj,)
    if gl:
        return gl[0]


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

    projdir = getSumoProjDir(project)
    if projdir:
        setupPy = os.path.join(projdir, 'setup.py')
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
    """
    Delegate setup.py functionality to individual subproject setup.py scripts.

    If we are running from a Sumo tarball, the TwistedCore-* directory
    will be added to PYTHONPATH so setup.py scripts can use
    functionality from Twisted.
    """
    os.environ["PYTHONPATH"] = "." + os.pathsep + os.getenv("PYTHONPATH", "")
    if len(args) == 0 or args[0] in ('-h', '--help'):
        sys.stdout.write(
"""Twisted: The Framework Of Your Internet.
Usage: setup.py <distutils args..>
""")
        runSetup('core', ['-h'])
        sys.exit(0)

    # If we've got a sumo ball, we should insert the Core directory
    # into sys.path because setup.py files try to import
    # twisted.python.dist.
    coredir = getSumoProjDir("core")
    if coredir and os.path.exists(coredir):
        os.environ["PYTHONPATH"] += os.pathsep + os.path.abspath(coredir)

    for project in sumoSubprojects:
        runSetup(project, args)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
