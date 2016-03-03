# -*- test-case-name: twisted.python.test.test_release -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Twisted's automated release system.

This module is only for use within Twisted's release system. If you are anyone
else, do not use it. The interface and behaviour will change without notice.

Only Linux is supported by this code.  It should not be used by any tools
which must run on multiple platforms (eg the setup.py script).
"""

import os
import re
import sys
import textwrap

from zope.interface import Interface, implementer

from datetime import date
from subprocess import PIPE, STDOUT, Popen

from twisted.python.versions import Version
from twisted.python.filepath import FilePath
from twisted.python.compat import execfile
from twisted.python.usage import Options, UsageError

# The offset between a year and the corresponding major version number.
VERSION_OFFSET = 2000


def runCommand(args, cwd=None):
    """
    Execute a vector of arguments.

    @type args: L{list} of L{bytes}
    @param args: A list of arguments, the first of which will be used as the
        executable to run.

    @type cwd: L{bytes}
    @param: The current working directory that the command should run with.

    @rtype: L{bytes}
    @return: All of the standard output.

    @raise CommandFailed: when the program exited with a non-0 exit code.
    """
    process = Popen(args, stdout=PIPE, stderr=STDOUT, cwd=cwd)
    stdout = process.stdout.read()
    exitCode = process.wait()
    if exitCode < 0:
        raise CommandFailed(None, -exitCode, stdout)
    elif exitCode > 0:
        raise CommandFailed(exitCode, None, stdout)
    return stdout



class CommandFailed(Exception):
    """
    Raised when a child process exits unsuccessfully.

    @type exitStatus: C{int}
    @ivar exitStatus: The exit status for the child process.

    @type exitSignal: C{int}
    @ivar exitSignal: The exit signal for the child process.

    @type output: C{str}
    @ivar output: The bytes read from stdout and stderr of the child process.
    """
    def __init__(self, exitStatus, exitSignal, output):
        Exception.__init__(self, exitStatus, exitSignal, output)
        self.exitStatus = exitStatus
        self.exitSignal = exitSignal
        self.output = output



class IVCSCommand(Interface):
    """
    An interface for VCS commands.
    """
    def ensureIsWorkingDirectory(path):
        """
        Ensure that C{path} is a working directory of this VCS.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to check.
        """


    def isStatusClean(path):
        """
        Return the Git status of the files in the specified path.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to get the status from (can be a directory or a
            file.)
        """


    def remove(path):
        """
        Remove the specified path from a the VCS.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to remove from the repository.
        """


    def exportTo(fromDir, exportDir):
        """
        Export the content of the VCSrepository to the specified directory.

        @type fromDir: L{twisted.python.filepath.FilePath}
        @param fromDir: The path to the VCS repository to export.

        @type exportDir: L{twisted.python.filepath.FilePath}
        @param exportDir: The directory to export the content of the
            repository to. This directory doesn't have to exist prior to
            exporting the repository.
        """



@implementer(IVCSCommand)
class GitCommand(object):
    """
    Subset of Git commands to release Twisted from a Git repository.
    """
    @staticmethod
    def ensureIsWorkingDirectory(path):
        """
        Ensure that C{path} is a Git working directory.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to check.
        """
        try:
            runCommand(["git", "rev-parse"], cwd=path.path)
        except (CommandFailed, OSError):
            raise NotWorkingDirectory(
                "%s does not appear to be a Git repository."
                % (path.path,))


    @staticmethod
    def isStatusClean(path):
        """
        Return the Git status of the files in the specified path.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to get the status from (can be a directory or a
            file.)
        """
        status = runCommand(
            ["git", "-C", path.path, "status", "--short"]).strip()
        return status == ''


    @staticmethod
    def remove(path):
        """
        Remove the specified path from a Git repository.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to remove from the repository.
        """
        runCommand(["git", "-C", path.dirname(), "rm", path.path])


    @staticmethod
    def exportTo(fromDir, exportDir):
        """
        Export the content of a Git repository to the specified directory.

        @type fromDir: L{twisted.python.filepath.FilePath}
        @param fromDir: The path to the Git repository to export.

        @type exportDir: L{twisted.python.filepath.FilePath}
        @param exportDir: The directory to export the content of the
            repository to. This directory doesn't have to exist prior to
            exporting the repository.
        """
        runCommand(["git", "-C", fromDir.path,
                    "checkout-index", "--all", "--force",
                    # prefix has to end up with a "/" so that files get copied
                    # to a directory whose name is the prefix.
                    "--prefix", exportDir.path + "/"])



@implementer(IVCSCommand)
class SVNCommand(object):
    """
    Subset of SVN commands to release Twisted from a Subversion checkout.
    """
    @staticmethod
    def ensureIsWorkingDirectory(path):
        """
        Ensure that C{path} is a SVN working directory.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to check.
        """
        if "is not a working copy" in runCommand(
                ["svn", "status", path.path]):
            raise NotWorkingDirectory(
                "%s does not appear to be an SVN working directory."
                % (path.path,))


    @staticmethod
    def isStatusClean(path):
        """
        Return the SVN status of the files in the specified path.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to get the status from (can be a directory or a
            file.)
        """
        status = runCommand(["svn", "status", path.path]).strip()
        return status == ''


    @staticmethod
    def remove(path):
        """
        Remove the specified path from a Subversion checkout.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to remove from the checkout.
        """
        runCommand(["svn", "rm", path.path])


    @staticmethod
    def exportTo(fromDir, exportDir):
        """
        Export the content of a SVN checkout to the specified directory.

        @type fromDir: L{twisted.python.filepath.FilePath}
        @param fromDir: The path to the Subversion checkout to export.

        @type exportDir: L{twisted.python.filepath.FilePath}
        @param exportDir: The directory to export the content of the checkout
            to. This directory doesn't have to exist prior to exporting the
            repository.
        """
        runCommand(["svn", "export", fromDir.path, exportDir.path])



def getRepositoryCommand(directory):
    """
    Detect the VCS used in the specified directory and return either a
    L{SVNCommand} or a L{GitCommand} if the directory is a Subversion checkout
    or a Git repository, respectively.
    If the directory is neither one nor the other, it raises a
    L{NotWorkingDirectory} exception.

    @type directory: L{FilePath}
    @param directory: The directory to detect the VCS used from.

    @rtype: L{SVNCommand} or L{GitCommand}

    @raise NotWorkingDirectory: if no supported VCS can be found from the
        specified directory.
    """
    try:
        SVNCommand.ensureIsWorkingDirectory(directory)
        return SVNCommand
    except (NotWorkingDirectory, OSError):
        # It's not SVN, but that's okay, eat the error
        pass

    try:
        GitCommand.ensureIsWorkingDirectory(directory)
        return GitCommand
    except (NotWorkingDirectory, OSError):
        # It's not Git, but that's okay, eat the error
        pass

    raise NotWorkingDirectory("No supported VCS can be found in %s" %
                              (directory.path,))



def _changeVersionInFile(old, new, filename):
    """
    Replace the C{old} version number with the C{new} one in the given
    C{filename}.
    """
    replaceInFile(filename, {old.base(): new.base()})



def getNextVersion(version, prerelease, patch, today):
    """
    Calculate the version number for a new release of Twisted based on
    the previous version number.

    @param version: The previous version number.

    @type prerelease: C{bool}
    @param prerelease: If C{True}, make the next version a pre-release one. If
       C{version} is a pre-release, it increments the pre-release counter,
       otherwise create a new version with prerelease set to 1.

    @type patch: C{bool}
    @param patch: If C{True}, make the next version a patch release. It
        increments the micro counter.

    @type today: C{datetime}
    @param today: The current date.
    """
    micro = 0
    major = today.year - VERSION_OFFSET
    if major != version.major:
        minor = 0
    else:
        minor = version.minor + 1

    if patch:
        micro = version.micro + 1
        major = version.major
        minor = version.minor

    newPrerelease = None
    if version.prerelease is not None:
        major = version.major
        minor = version.minor
        micro = version.micro
        if prerelease:
            newPrerelease = version.prerelease + 1
    elif prerelease:
        newPrerelease = 1
    return Version(version.package, major, minor, micro, newPrerelease)



def changeAllProjectVersions(root, prerelease, patch, today=None):
    """
    Change the version of the project.

    @type root: L{FilePath}
    @param root: The root of the Twisted source tree.

    @type prerelease: C{bool}
    @param prerelease:

    @type patch: C{bool}
    @param patch:

    @type today: C{datetime}
    @param today: Defaults to the current day, according to the system clock.
    """
    if not today:
        today = date.today()
    formattedToday = today.strftime('%Y-%m-%d')

    twistedProject = Project(root.child("twisted"))
    oldVersion = twistedProject.getVersion()
    newVersion = getNextVersion(oldVersion, prerelease, patch, today)

    def _makeNews(project, underTopfiles=True):
        builder = NewsBuilder()
        builder._changeNewsVersion(
            root.child("NEWS"), builder._getNewsName(project),
            oldVersion, newVersion, formattedToday)
        if underTopfiles:
            builder._changeNewsVersion(
                project.directory.child("topfiles").child("NEWS"),
                builder._getNewsName(project), oldVersion, newVersion,
                formattedToday)

    if oldVersion.prerelease:
        _makeNews(twistedProject, underTopfiles=False)

    for project in findTwistedProjects(root):
        if oldVersion.prerelease:
            _makeNews(project)
        project.updateREADME(newVersion)

    # Then change the global version.
    twistedProject.updateVersion(newVersion)
    _changeVersionInFile(oldVersion, newVersion, root.child('README.rst').path)



class Project(object):
    """
    A representation of a project that has a version.

    @ivar directory: A L{twisted.python.filepath.FilePath} pointing to the base
        directory of a Twisted-style Python package. The package should contain
        a C{_version.py} file and a C{topfiles} directory that contains a
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
        directory = self.directory
        while not namespace:
            if directory.path == "/":
                raise Exception("Not inside a Twisted project.")
            elif not directory.basename() == "twisted":
                directory = directory.parent()
            else:
                execfile(directory.child("_version.py").path, namespace)
        return namespace["version"]


    def updateVersion(self, version):
        """
        Replace the existing version numbers in _version.py and README files
        with the specified version.

        @param version: The version to update to.
        """
        if not self.directory.basename() == "twisted":
            raise Exception("Can't change the version of subprojects.")

        oldVersion = self.getVersion()
        replaceProjectVersion(self.directory.child("_version.py").path,
                              version)
        _changeVersionInFile(
            oldVersion, version,
            self.directory.child("topfiles").child("README").path)


    def updateREADME(self, version):
        """
        Replace the existing version numbers in the README file with the
        specified version.

        @param version: The version to update to.
        """
        oldVersion = self.getVersion()
        _changeVersionInFile(
            oldVersion, version,
            self.directory.child("topfiles").child("README").path)



def findTwistedProjects(baseDirectory):
    """
    Find all Twisted-style projects beneath a base directory.

    @param baseDirectory: A L{twisted.python.filepath.FilePath} to look inside.
    @return: A list of L{Project}.
    """
    projects = []
    for filePath in baseDirectory.walk():
        if filePath.basename() == 'topfiles':
            projectDirectory = filePath.parent()
            projects.append(Project(projectDirectory))
    return projects



def generateVersionFileData(version):
    """
    Generate the data to be placed into a _version.py file.

    @param version: A version object.
    """
    if version.prerelease is not None:
        prerelease = ", prerelease=%r" % (version.prerelease,)
    else:
        prerelease = ""
    data = '''\
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

# This is an auto-generated file. Do not edit it.

"""
Provides Twisted version information.
"""

from twisted.python import versions
version = versions.Version(%r, %s, %s, %s%s)
''' % (version.package, version.major, version.minor, version.micro,
       prerelease)
    return data



def replaceProjectVersion(filename, newversion):
    """
    Write version specification code into the given filename, which
    sets the version to the given version number.

    @param filename: A filename which is most likely a "_version.py"
        under some Twisted project.
    @param newversion: A version object.
    """
    # XXX - this should be moved to Project and renamed to writeVersionFile.
    # jml, 2007-11-15.
    f = open(filename, 'w')
    f.write(generateVersionFileData(newversion))
    f.close()



def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using science.
    """
    os.rename(filename, filename + '.bak')
    f = open(filename + '.bak')
    d = f.read()
    f.close()
    for k, v in oldToNew.items():
        d = d.replace(k, v)
    f = open(filename + '.new', 'w')
    f.write(d)
    f.close()
    os.rename(filename + '.new', filename)
    os.unlink(filename + '.bak')



class NoDocumentsFound(Exception):
    """
    Raised when no input documents are found.
    """



class APIBuilder(object):
    """
    Generate API documentation from source files using
    U{pydoctor<http://codespeak.net/~mwh/pydoctor/>}.  This requires
    pydoctor to be installed and usable.
    """
    def build(self, projectName, projectURL, sourceURL, packagePath,
              outputPath):
        """
        Call pydoctor's entry point with options which will generate HTML
        documentation for the specified package's API.

        @type projectName: C{str}
        @param projectName: The name of the package for which to generate
            documentation.

        @type projectURL: C{str}
        @param projectURL: The location (probably an HTTP URL) of the project
            on the web.

        @type sourceURL: C{str}
        @param sourceURL: The location (probably an HTTP URL) of the root of
            the source browser for the project.

        @type packagePath: L{FilePath}
        @param packagePath: The path to the top-level of the package named by
            C{projectName}.

        @type outputPath: L{FilePath}
        @param outputPath: An existing directory to which the generated API
            documentation will be written.
        """
        from pydoctor.driver import main
        main(
            ["--project-name", projectName,
             "--project-url", projectURL,
             "--system-class", "pydoctor.twistedmodel.TwistedSystem",
             "--project-base-dir", packagePath.parent().path,
             "--html-viewsource-base", sourceURL,
             "--add-package", packagePath.path,
             "--html-output", outputPath.path,
             "--html-write-function-pages", "--quiet", "--make-html"])



class NewsBuilder(object):
    """
    Generate the new section of a NEWS file.

    The C{_FEATURE}, C{_BUGFIX}, C{_DOC}, C{_REMOVAL}, and C{_MISC}
    attributes of this class are symbolic names for the news entry types
    which are supported.  Conveniently, they each also take on the value of
    the file name extension which indicates a news entry of that type.

    @cvar _headings: A C{dict} mapping one of the news entry types to the
        heading to write out for that type of news entry.

    @cvar _NO_CHANGES: A C{str} giving the text which appears when there are
        no significant changes in a release.

    @cvar _TICKET_HINT: A C{str} giving the text which appears at the top of
        each news file and which should be kept at the top, not shifted down
        with all the other content.  Put another way, this is the text after
        which the new news text is inserted.
    """

    _FEATURE = ".feature"
    _BUGFIX = ".bugfix"
    _DOC = ".doc"
    _REMOVAL = ".removal"
    _MISC = ".misc"

    _headings = {
        _FEATURE: "Features",
        _BUGFIX: "Bugfixes",
        _DOC: "Improved Documentation",
        _REMOVAL: "Deprecations and Removals",
        _MISC: "Other"}

    _NO_CHANGES = "No significant changes have been made for this release.\n"

    _TICKET_HINT = (
        'Ticket numbers in this file can be looked up by visiting\n'
        'http://twistedmatrix.com/trac/ticket/<number>\n'
        '\n')

    def _today(self):
        """
        Return today's date as a string in YYYY-MM-DD format.
        """
        return date.today().strftime('%Y-%m-%d')


    def _findChanges(self, path, ticketType):
        """
        Load all the feature ticket summaries.

        @param path: A L{FilePath} the direct children of which to search
            for news entries.

        @param ticketType: The type of news entries to search for.  One of
            L{NewsBuilder._FEATURE}, L{NewsBuilder._BUGFIX},
            L{NewsBuilder._REMOVAL}, or L{NewsBuilder._MISC}.

        @return: A C{list} of two-tuples.  The first element is the ticket
            number as an C{int}.  The second element of each tuple is the
            description of the feature.
        """
        results = []
        for child in path.children():
            base, ext = os.path.splitext(child.basename())
            if ext == ticketType:
                results.append((
                    int(base),
                    ' '.join(child.getContent().splitlines())))
        results.sort()
        return results


    def _formatHeader(self, header):
        """
        Format a header for a NEWS file.

        A header is a title with '=' signs underlining it.

        @param header: The header string to format.
        @type header: C{str}
        @return: A C{str} containing C{header}.
        """
        return header + '\n' + '=' * len(header) + '\n\n'


    def _writeHeader(self, fileObj, header):
        """
        Write a version header to the given file.

        @param fileObj: A file-like object to which to write the header.
        @param header: The header to write to the file.
        @type header: C{str}
        """
        fileObj.write(self._formatHeader(header))


    def _writeSection(self, fileObj, header, tickets):
        """
        Write out one section (features, bug fixes, etc) to the given file.

        @param fileObj: A file-like object to which to write the news section.

        @param header: The header for the section to write.
        @type header: C{str}

        @param tickets: A C{list} of ticket information of the sort returned
            by L{NewsBuilder._findChanges}.
        """
        if not tickets:
            return

        reverse = {}
        for (ticket, description) in tickets:
            reverse.setdefault(description, []).append(ticket)
        for description in reverse:
            reverse[description].sort()
        reverse = reverse.items()
        reverse.sort(key=lambda (descr, tickets): tickets[0])

        fileObj.write(header + '\n' + '-' * len(header) + '\n')
        for (description, relatedTickets) in reverse:
            ticketList = ', '.join([
                '#' + str(ticket) for ticket in relatedTickets])
            entry = ' - %s (%s)' % (description, ticketList)
            entry = textwrap.fill(entry, subsequent_indent='   ')
            fileObj.write(entry + '\n')
        fileObj.write('\n')


    def _writeMisc(self, fileObj, header, tickets):
        """
        Write out a miscellaneous-changes section to the given file.

        @param fileObj: A file-like object to which to write the news section.

        @param header: The header for the section to write.
        @type header: C{str}

        @param tickets: A C{list} of ticket information of the sort returned
            by L{NewsBuilder._findChanges}.
        """
        if not tickets:
            return

        fileObj.write(header + '\n' + '-' * len(header) + '\n')
        formattedTickets = []
        for (ticket, ignored) in tickets:
            formattedTickets.append('#' + str(ticket))
        entry = ' - ' + ', '.join(formattedTickets)
        entry = textwrap.fill(entry, subsequent_indent='   ')
        fileObj.write(entry + '\n\n')


    def build(self, path, output, header):
        """
        Load all of the change information from the given directory and write
        it out to the given output file.

        @param path: A directory (probably a I{topfiles} directory) containing
            change information in the form of <ticket>.<change type> files.
        @type path: L{FilePath}

        @param output: The NEWS file to which the results will be prepended.
        @type output: L{FilePath}

        @param header: The top-level header to use when writing the news.
        @type header: L{str}

        @raise NotWorkingDirectory: If the C{path} is not a supported VCS
            repository.
        """
        changes = []
        for part in (self._FEATURE, self._BUGFIX, self._DOC, self._REMOVAL):
            tickets = self._findChanges(path, part)
            if tickets:
                changes.append((part, tickets))
        misc = self._findChanges(path, self._MISC)

        oldNews = output.getContent()
        newNews = output.sibling('NEWS.new').open('w')
        if oldNews.startswith(self._TICKET_HINT):
            newNews.write(self._TICKET_HINT)
            oldNews = oldNews[len(self._TICKET_HINT):]

        self._writeHeader(newNews, header)
        if changes:
            for (part, tickets) in changes:
                self._writeSection(newNews, self._headings.get(part), tickets)
        else:
            newNews.write(self._NO_CHANGES)
            newNews.write('\n')
        self._writeMisc(newNews, self._headings.get(self._MISC), misc)
        newNews.write('\n')
        newNews.write(oldNews)
        newNews.close()
        output.sibling('NEWS.new').moveTo(output)


    def _deleteFragments(self, path):
        """
        Delete the change information, to clean up the repository  once the
        NEWS files have been built. It requires C{path} to be in a supported
        VCS repository.

        @param path: A directory (probably a I{topfiles} directory) containing
            change information in the form of <ticket>.<change type> files.
        @type path: L{FilePath}
        """
        cmd = getRepositoryCommand(path)
        ticketTypes = self._headings.keys()
        for child in path.children():
            base, ext = os.path.splitext(child.basename())
            if ext in ticketTypes:
                cmd.remove(child)


    def _getNewsName(self, project):
        """
        Return the name of C{project} that should appear in NEWS.

        @param project: A L{Project}
        @return: The name of C{project}.
        """
        name = project.directory.basename().title()
        if name == 'Twisted':
            name = 'Core'
        return name


    def _iterProjects(self, baseDirectory):
        """
        Iterate through the Twisted projects in C{baseDirectory}, yielding
        everything we need to know to build news for them.

        Yields C{topfiles}, C{name}, C{version}, for each sub-project in
        reverse-alphabetical order. C{topfile} is the L{FilePath} for the
        topfiles directory, C{name} is the nice name of the project (as should
        appear in the NEWS file), C{version} is the current version string for
        that project.

        @param baseDirectory: A L{FilePath} representing the root directory
            beneath which to find Twisted projects for which to generate
            news (see L{findTwistedProjects}).
        @type baseDirectory: L{FilePath}
        """
        # Get all the subprojects to generate news for
        projects = findTwistedProjects(baseDirectory)
        # And order them alphabetically for ease of reading
        projects.sort(key=lambda proj: proj.directory.path)
        # And generate them backwards since we write news by prepending to
        # files.
        projects.reverse()

        for project in projects:
            topfiles = project.directory.child("topfiles")
            name = self._getNewsName(project)
            version = project.getVersion()
            yield topfiles, name, version


    def buildAll(self, baseDirectory):
        """
        Find all of the Twisted subprojects beneath C{baseDirectory} and update
        their news files from the ticket change description files in their
        I{topfiles} directories and update the news file in C{baseDirectory}
        with all of the news.

        @param baseDirectory: A L{FilePath} representing the root directory
            beneath which to find Twisted projects for which to generate
            news (see L{findTwistedProjects}).
        """
        cmd = getRepositoryCommand(baseDirectory)
        cmd.ensureIsWorkingDirectory(baseDirectory)

        today = self._today()
        for topfiles, name, version in self._iterProjects(baseDirectory):
            # We first build for the subproject
            news = topfiles.child("NEWS")
            header = "Twisted %s %s (%s)" % (name, version.base(), today)
            self.build(topfiles, news, header)
            # Then for the global NEWS file
            news = baseDirectory.child("NEWS")
            self.build(topfiles, news, header)
            # Finally, delete the fragments
            self._deleteFragments(topfiles)


    def _changeNewsVersion(self, news, name, oldVersion, newVersion, today):
        """
        Change all references to the current version number in a NEWS file to
        refer to C{newVersion} instead.

        @param news: The NEWS file to change.
        @type news: L{FilePath}
        @param name: The name of the project to change.
        @type name: C{str}
        @param oldVersion: The old version of the project.
        @type oldVersion: L{Version}
        @param newVersion: The new version of the project.
        @type newVersion: L{Version}
        @param today: A YYYY-MM-DD string representing today's date.
        @type today: C{str}
        """
        newHeader = self._formatHeader(
            "Twisted %s %s (%s)" % (name, newVersion.base(), today))
        expectedHeaderRegex = re.compile(
            r"Twisted %s %s \(\d{4}-\d\d-\d\d\)\n=+\n\n" % (
                re.escape(name), re.escape(oldVersion.base())))
        oldNews = news.getContent()
        match = expectedHeaderRegex.search(oldNews)
        if match:
            oldHeader = match.group()
            replaceInFile(news.path, {oldHeader: newHeader})


    def main(self, args):
        """
        Build all news files.

        @param args: The command line arguments to process.  This must contain
            one string, the path to the base of the Twisted checkout for which
            to build the news.
        @type args: C{list} of C{str}
        """
        if len(args) != 1:
            sys.exit("Must specify one argument: the path to the "
                     "Twisted checkout")
        self.buildAll(FilePath(args[0]))



class SphinxBuilder(object):
    """
    Generate HTML documentation using Sphinx.

    Generates and runs a shell command that looks something like::

        sphinx-build -b html -d [BUILDDIR]/doctrees
                                [DOCDIR]/source
                                [BUILDDIR]/html

    where DOCDIR is a directory containing another directory called "source"
    which contains the Sphinx source files, and BUILDDIR is the directory in
    which the Sphinx output will be created.
    """

    def main(self, args):
        """
        Build the main documentation.

        @type args: list of str
        @param args: The command line arguments to process.  This must contain
            one string argument: the path to the root of a Twisted checkout.
            Additional arguments will be ignored for compatibility with legacy
            build infrastructure.
        """
        output = self.build(FilePath(args[0]).child("docs"))
        if output:
            sys.stdout.write("Unclean build:\n{}\n".format(output))
            raise sys.exit(1)


    def build(self, docDir, buildDir=None, version=''):
        """
        Build the documentation in C{docDir} with Sphinx.

        @param docDir: The directory of the documentation.  This is a directory
            which contains another directory called "source" which contains the
            Sphinx "conf.py" file and sphinx source documents.
        @type docDir: L{twisted.python.filepath.FilePath}

        @param buildDir: The directory to build the documentation in.  By
            default this will be a child directory of {docDir} named "build".
        @type buildDir: L{twisted.python.filepath.FilePath}

        @param version: The version of Twisted to set in the docs.
        @type version: C{str}

        @return: the output produced by running the command
        @rtype: L{str}
        """
        if buildDir is None:
            buildDir = docDir.parent().child('doc')

        doctreeDir = buildDir.child('doctrees')

        output = runCommand(['sphinx-build', '-q', '-b', 'html',
                             '-d', doctreeDir.path, docDir.path,
                             buildDir.path])

        # Delete the doctrees, as we don't want them after the docs are built
        doctreeDir.remove()

        for path in docDir.walk():
            if path.basename() == "man":
                segments = path.segmentsFrom(docDir)
                dest = buildDir
                while segments:
                    dest = dest.child(segments.pop(0))
                if not dest.parent().isdir():
                    dest.parent().makedirs()
                path.copyTo(dest)
        return output



def filePathDelta(origin, destination):
    """
    Return a list of strings that represent C{destination} as a path relative
    to C{origin}.

    It is assumed that both paths represent directories, not files. That is to
    say, the delta of L{twisted.python.filepath.FilePath} /foo/bar to
    L{twisted.python.filepath.FilePath} /foo/baz will be C{../baz},
    not C{baz}.

    @type origin: L{twisted.python.filepath.FilePath}
    @param origin: The origin of the relative path.

    @type destination: L{twisted.python.filepath.FilePath}
    @param destination: The destination of the relative path.
    """
    commonItems = 0
    path1 = origin.path.split(os.sep)
    path2 = destination.path.split(os.sep)
    for elem1, elem2 in zip(path1, path2):
        if elem1 == elem2:
            commonItems += 1
        else:
            break
    path = [".."] * (len(path1) - commonItems)
    return path + path2[commonItems:]



class NotWorkingDirectory(Exception):
    """
    Raised when a directory does not appear to be a repository directory of a
    supported VCS.
    """



class ChangeVersionsScriptOptions(Options):
    """
    Options for L{ChangeVersionsScript}.
    """
    optFlags = [["prerelease", None, "Change to the next prerelease"],
                ["patch", None, "Make a patch version"]]



class ChangeVersionsScript(object):
    """
    A thing for changing version numbers. See L{main}.
    """
    changeAllProjectVersions = staticmethod(changeAllProjectVersions)

    def main(self, args):
        """
        Given a list of command-line arguments, change all the Twisted versions
        in the current directory.

        @type args: list of str
        @param args: List of command line arguments.  This should only
            contain the version number.
        """
        options = ChangeVersionsScriptOptions()

        try:
            options.parseOptions(args)
        except UsageError as e:
            raise SystemExit(e)

        self.changeAllProjectVersions(FilePath("."), options["prerelease"],
                                      options["patch"])



class BuildAPIDocsScript(object):
    """
    A thing for building API documentation. See L{main}.
    """

    def buildAPIDocs(self, projectRoot, output):
        """
        Build the API documentation of Twisted, with our project policy.

        @param projectRoot: A L{FilePath} representing the root of the Twisted
            checkout.
        @param output: A L{FilePath} pointing to the desired output directory.
        """
        version = Project(projectRoot.child("twisted")).getVersion()
        versionString = version.base()
        sourceURL = ("http://twistedmatrix.com/trac/browser/tags/releases/"
                     "twisted-%s" % (versionString,))
        apiBuilder = APIBuilder()
        apiBuilder.build(
            "Twisted",
            "http://twistedmatrix.com/",
            sourceURL,
            projectRoot.child("twisted"),
            output)


    def main(self, args):
        """
        Build API documentation.

        @type args: list of str
        @param args: The command line arguments to process.  This must contain
            two strings: the path to the root of the Twisted checkout, and a
            path to an output directory.
        """
        if len(args) != 2:
            sys.exit("Must specify two arguments: "
                     "Twisted checkout and destination path")
        self.buildAPIDocs(FilePath(args[0]), FilePath(args[1]))
