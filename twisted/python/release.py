"""
A release-automation toolkit.

API Stability: Unstable. Don't use it outside of Twisted.

Maintainer: U{Christopher Armstrong<mailto:radix@twistedmatrix.com>}
"""

import os
from os.path import join as opj
import re

from twisted.python import dist



# errors

class DirectoryExists(OSError):
    """Some directory exists when it shouldn't."""
    pass



class DirectoryDoesntExist(OSError):
    """Some directory doesn't exist when it should."""
    pass



class CommandFailed(OSError):
    pass



# utilities

def sh(command, null=True, prompt=False):
    """
    I'll try to execute `command', and if `prompt' is true, I'll
    ask before running it.  If the command returns something other
    than 0, I'll raise CommandFailed(command).
    """
    print "--$", command

    if prompt:
        if raw_input("run ?? ").startswith('n'):
            return
    if null:
        command = "%s > /dev/null" % command
    if os.system(command) != 0:
        raise CommandFailed(command)



def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using sed
    and mv.
    """
    os.rename(filename, filename+'.bak')
    f = open(filename+'.bak')
    d = f.read()
    f.close()
    for k,v in oldToNew.items():
        d = d.replace(k, v)
    f = open(filename + '.new', 'w')
    f.write(d)
    f.close()
    os.rename(filename+'.new', filename)
    os.unlink(filename+'.bak')



def runChdirSafe(f, *args, **kw):
    origdir = os.path.abspath('.')
    try:
        return f(*args, **kw)
    finally:
        os.chdir(origdir)



class Project:
    """
    A representation of a Twisted project with version information.
    """
    newVersion = None
    versionfile = None
    name = None
    pkgname = None
    currentVersionStr = None
    dir = None

    def __init__(self, **kw):
        self.__dict__.update(kw)


    def fullyQualifiedName(self):
        """
        Return a string naming the project: e.g. "Twisted", 
        "Twisted Conch", etc.
        """
        if self.name == "twisted":
            return "Twisted"
        return "Twisted %s" % (self.name.capitalize(),)



class Done(Exception):
    """
    Raised when the user is done answering questions.
    """
    pass



verstringMatcher = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)$")

def inputNewVersion(project):
    """
    Ask the user to input a new version number for the given project,
    and return a three-tuple of (major, minor, micro).
    """
    match = None
    while match is None:
        new_vers = raw_input("New version for %s? " % (project.name))
        if not new_vers:
            return None
        if new_vers == 'done':
            raise Done
        match = verstringMatcher.match(new_vers)
        if match is None:
            print 'Invalid format. Use e.g. 2.0.0.'

    major, minor, micro = map(int, match.groups())

    return major, minor, micro



def getVersionSafely(proj):
    """
    Call dist.getVersion, and if an error is raised, return None.
    """
    try:
        currentVersionStr = dist.getVersion(proj)
    except:
        currentVersionStr = None
    return currentVersionStr



def gatherCurrentInfo():
    """
    @returns: A list of L{Project} instances with current information
    when available.
    """
    projects = [Project(name='twisted', pkgname='twisted',
                        versionfile='twisted/_version.py',
                        currentVersionStr=getVersionSafely('core'),
                        dir='twisted')]
    for pname in dist.twisted_subprojects:
        dir = opj('twisted', pname)
        pkgname = 'twisted.'+pname
        projects.append(
            Project(name=pname,
                    pkgname=pkgname,
                    dir=dir,
                    versionfile=opj(dir, '_version.py'),
                    currentVersionStr=getVersionSafely(pname),
                    )
            )
    return projects



def replaceProjectVersion(filename, newversion):
    """
    Write version specification code into the given filename, which
    sets the version to the given version number.

    @param filename: A filename which is most likely a "_version.py"
    under some Twisted project.
    @param newversion: A sequence of three numbers.
    """
    f = open(filename, 'w')
    f.write('''\
# This is an auto-generated file. Use admin/change-versions to update.
from twisted.python import versions
version = versions.Version(__name__[:__name__.rfind('.')], %s, %s, %s)
''' % tuple(newversion))
    f.close()
