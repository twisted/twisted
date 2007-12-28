# -*- test-case-name: twisted.python.test.test_release -*-
# Copyright (c) 2007 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted's automated release system.

This module is only for use within Twisted's release system. If you are anyone
else, do not use it. The interface and behaviour will change without notice.
"""

from datetime import date
import os

import twisted

from twisted.python.filepath import FilePath
from twisted.python.versions import Version

# This import is an example of why you shouldn't use this module unless you're
# radix
from twisted.lore.scripts import lore

# The offset between a year and the corresponding major version number.
VERSION_OFFSET = 2000


def _changeVersionInFile(old, new, filename):
    """
    Replace the C{old} version number with the C{new} one in the given
    C{filename}.
    """
    replaceInFile(filename, {old.base(): new.base()})



def getNextVersion(version, now=None):
    """
    Calculate the version number for a new release of Twisted based on
    the previous version number.

    @param version: The previous version number.
    @param now: (optional) The current date.
    """
    # XXX: This has no way of incrementing the patch number. Currently, we
    # don't need it. See bug 2915. Jonathan Lange, 2007-11-20.
    if now is None:
        now = date.today()
    major = now.year - VERSION_OFFSET
    if major != version.major:
        minor = 0
    else:
        minor = version.minor + 1
    return Version(version.package, major, minor, 0)



class Project(object):
    """
    A representation of a project that has a version.

    @ivar directory: A L{FilePath} pointing to the base directory of a
        Twisted-style Python package. The package should contain a
        C{_version.py} file and a C{topfiles} directory that contains a
        C{README} file.
    """

    def __init__(self, directory):
        self.directory = directory


    def __repr__(self):
        return '%s(%r)' % (
            self.__class__.__name__, self.directory)


    def getVersion(self):
        """
        @return: A L{Version} specifying the version number of the project
        based on live python modules.
        """
        namespace = {}
        execfile(self.directory.child("_version.py").path, namespace)
        return namespace["version"]


    def updateVersion(self, version):
        """
        Replace the existing version numbers in _version.py and README files
        with the specified version.
        """
        oldVersion = self.getVersion()
        replaceProjectVersion(oldVersion.package,
                              self.directory.child("_version.py").path,
                              (version.major, version.minor, version.micro))
        _changeVersionInFile(
            oldVersion, version,
            self.directory.child("topfiles").child("README").path)



def findTwistedProjects(baseDirectory):
    """
    Find all Twisted-style projects beneath a base directory.

    @param baseDirectory: A L{FilePath} to look inside.
    @return: A list of L{Project}.
    """
    projects = []
    for filePath in baseDirectory.walk():
        if filePath.basename() == 'topfiles':
            projectDirectory = filePath.parent()
            projects.append(Project(projectDirectory))
    return projects



def updateTwistedVersionInformation(baseDirectory, now):
    """
    Update the version information for Twisted and all subprojects to the
    date-based version number.

    @param baseDirectory: Where to look for Twisted. If None, the function
        infers the information from C{twisted.__file__}.
    @param now: The current date (as L{datetime.date}). If None, it defaults
        to today.
    """
    for project in findTwistedProjects(baseDirectory):
        project.updateVersion(getNextVersion(project.getVersion(), now=now))



def replaceProjectVersion(name, filename, newversion):
    """
    Write version specification code into the given filename, which
    sets the version to the given version number.

    @param filename: A filename which is most likely a "_version.py"
    under some Twisted project.
    @param newversion: A sequence of three numbers.
    """
    # XXX - this should be moved to Project and renamed to writeVersionFile.
    # jml, 2007-11-15.
    f = open(filename, 'w')
    f.write('''\
# This is an auto-generated file. Do not edit it.
from twisted.python import versions
version = versions.Version(%r, %s, %s, %s)
''' % ((name,) + tuple(newversion)))
    f.close()



def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using science.
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



class NoDocumentsFound(Exception):
    """
    Raised when no input documents are found.
    """


class DocBuilder(object):
    """
    Generate documentation for projects.
    """

    def build(self, version, resourceDir, docDir, template, deleteInput=False):
        """
        Build the documentation in C{docDir} with Lore.

        Input files ending in .xhtml will be considered. Output will written as
        .html files.

        @param version: the version of the documentation to pass to lore.
        @type version: C{str}

        @param resourceDir: The directory which contains the toplevel index and
            stylesheet file for this section of documentation.
        @type resourceDir: L{FilePath}

        @param docDir: The directory of the documentation.
        @type docDir: L{FilePath}

        @param template: The template used to generate the documentation.
        @type template: L{FilePath}

        @param deleteInput: If True, the input documents will be deleted after
            their output is generated.
        @type deleteInput: C{bool}

        @raise NoDocumentsFound: When there are no .xhtml files in the given
            C{docDir}.
        """
        linkrel = self.getLinkrel(resourceDir, docDir)
        options = lore.Options()
        inputFiles = docDir.globChildren("*.xhtml")
        filenames = [x.path for x in inputFiles]
        if not filenames:
            raise NoDocumentsFound("No input documents found in %s" % (docDir,))
        arguments = ["--null",
                     "--config", "template=%s" % (template.path,),
                     "--config", "ext=.html",
                     "--config", "version=%s" % (version,),
                     "--linkrel", linkrel] + filenames
        options.parseOptions(arguments)
        lore.runGivenOptions(options)
        if deleteInput:
            for inputFile in inputFiles:
                inputFile.remove()


    def getLinkrel(self, resourceDir, docDir):
        """
        Calculate a value appropriate for Lore's --linkrel option.

        Lore's --linkrel option defines how to 'find' documents that are
        linked to from TEMPLATE files (NOT document bodies). That is, it's a
        prefix for links ('a' and 'link') in the template.

        @param resourceDir: The directory which contains the toplevel index and
            stylesheet file for this section of documentation.
        @type resourceDir: L{FilePath}

        @param docDir: The directory containing documents that must link to
            C{resourceDir}.
        @type docDir: L{FilePath}
        """
        if resourceDir != docDir:
            return '/'.join(filePathDelta(docDir, resourceDir)) + "/"
        else:
            return ""



def filePathDelta(origin, destination):
    """
    Return a list of strings that represent C{destination} as a path relative
    to C{origin}.

    It is assumed that both paths represent directories, not files. That is to
    say, the delta of FilePath /foo/bar to FilePath /foo/baz will be C{../baz},
    not C{baz}.

    @type origin: L{FilePath}
    @param origin: The origin of the relative path.

    @type destination: L{FilePath}
    @param destination: The destination of the relative path.
    """
    commonItems = 0
    path1 = origin.path.split(os.sep)
    path2 = destination.path.split(os.sep)
    for elem1, elem2 in zip(path1, path2):
        if elem1 == elem2:
            commonItems += 1
    path = [".."] * (len(path1) - commonItems)
    return path + path2[commonItems:]
