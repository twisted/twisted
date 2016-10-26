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
import sys
import textwrap

from zope.interface import Interface, implementer

from datetime import date
from subprocess import check_output, STDOUT, CalledProcessError

from twisted.python.filepath import FilePath
from twisted.python.monkey import MonkeyPatcher

# Types of topfiles.
TOPFILE_TYPES = ["doc", "bugfix", "misc", "feature", "removal"]
intersphinxURLs = [
    "https://docs.python.org/2/objects.inv",
    "https://docs.python.org/3/objects.inv",
    "https://pyopenssl.readthedocs.io/en/stable/objects.inv",
    "https://twisted.github.io/constantly/docs/objects.inv",
    "https://hawkowl.github.io/incremental/docs/objects.inv",
    "https://python-hyper.org/h2/en/stable/objects.inv",
    "https://python-hyper.org/priority/en/stable/objects.inv",
    "https://docs.zope.org/zope.interface/objects.inv",
]


def runCommand(args, **kwargs):
    """Execute a vector of arguments.

    This is a wrapper around L{subprocess.check_output}, so it takes
    the same arguments as L{subprocess.Popen} with one difference: all
    arguments after the vector must be keyword arguments.
    """
    kwargs['stderr'] = STDOUT
    return check_output(args, **kwargs)



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
        except (CalledProcessError, OSError):
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



def getRepositoryCommand(directory):
    """
    Detect the VCS used in the specified directory and return a L{GitCommand}
    if the directory is a Git repository. If the directory is not git, it
    raises a L{NotWorkingDirectory} exception.

    @type directory: L{FilePath}
    @param directory: The directory to detect the VCS used from.

    @rtype: L{GitCommand}

    @raise NotWorkingDirectory: if no supported VCS can be found from the
        specified directory.
    """
    try:
        GitCommand.ensureIsWorkingDirectory(directory)
        return GitCommand
    except (NotWorkingDirectory, OSError):
        # It's not Git, but that's okay, eat the error
        pass

    raise NotWorkingDirectory("No supported VCS can be found in %s" %
                              (directory.path,))



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
        @return: A L{incremental.Version} specifying the version number of the
            project based on live python modules.
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
        return namespace["__version__"]



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


def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using science.
    """
    os.rename(filename, filename + '.bak')
    with open(filename + '.bak') as f:
        d = f.read()
    for k, v in oldToNew.items():
        d = d.replace(k, v)
    with open(filename + '.new', 'w') as f:
        f.write(d)
    os.rename(filename + '.new', filename)
    os.unlink(filename + '.bak')



class NoDocumentsFound(Exception):
    """
    Raised when no input documents are found.
    """



class APIBuilder(object):
    """
    Generate API documentation from source files using
    U{pydoctor<https://github.com/twisted/pydoctor>}.  This requires
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
        intersphinxes = []

        for intersphinx in intersphinxURLs:
            intersphinxes.append("--intersphinx")
            intersphinxes.append(intersphinx)

        # Super awful monkeypatch that will selectively use our templates.
        from pydoctor.templatewriter import util
        originalTemplatefile = util.templatefile

        def templatefile(filename):

            if filename in ["summary.html", "index.html", "common.html"]:
                twistedPythonDir = FilePath(__file__).parent()
                templatesDir = twistedPythonDir.child("_pydoctortemplates")
                return templatesDir.child(filename).path
            else:
                return originalTemplatefile(filename)

        monkeyPatch = MonkeyPatcher((util, "templatefile", templatefile))
        monkeyPatch.patch()

        from pydoctor.driver import main

        main(
            ["--project-name", projectName,
             "--project-url", projectURL,
             "--system-class", "twisted.python._pydoctor.TwistedSystem",
             "--project-base-dir", packagePath.parent().path,
             "--html-viewsource-base", sourceURL,
             "--add-package", packagePath.path,
             "--html-output", outputPath.path,
             "--html-write-function-pages", "--quiet", "--make-html",
            ] + intersphinxes)

        monkeyPatch.restore()


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
            C{NewsBuilder._FEATURE}, C{NewsBuilder._BUGFIX},
            C{NewsBuilder._REMOVAL}, or C{NewsBuilder._MISC}.

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
        # result is a tuple of (descr, tickets)
        reverse.sort(key=lambda result: result[1][0])

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
        with output.sibling('NEWS.new').open('w') as newNews:
            if oldNews.startswith(self._TICKET_HINT):
                newNews.write(self._TICKET_HINT)
                oldNews = oldNews[len(self._TICKET_HINT):]

            self._writeHeader(newNews, header)
            if changes:
                for (part, tickets) in changes:
                    self._writeSection(newNews, self._headings.get(part),
                                       tickets)
            else:
                newNews.write(self._NO_CHANGES)
                newNews.write('\n')
            self._writeMisc(newNews, self._headings.get(self._MISC), misc)
            newNews.write('\n')
            newNews.write(oldNews)
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
        version = Project(
            projectRoot.child("twisted")).getVersion()
        versionString = version.base()
        sourceURL = ("https://github.com/twisted/twisted/tree/"
                     "twisted-%s" % (versionString,) + "/src")
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



class CheckTopfileScript(object):
    """
    A thing for checking whether a checkout has a topfile.
    """
    def __init__(self, _print):
        self._print = _print


    def main(self, args):
        """
        Run the script.

        @type args: L{list} of L{str}
        @param args: The command line arguments to process. This must contain
            one string: the path to the root of the Twisted checkout.
        """
        if len(args) != 1:
            sys.exit("Must specify one argument: the Twisted checkout")

        location = os.path.abspath(args[0])

        branch = runCommand([b"git", b"rev-parse", b"--abbrev-ref",  "HEAD"],
                            cwd=location).strip()

        r = runCommand([b"git", b"diff", b"--name-only", b"origin/trunk..."],
                       cwd=location).strip()

        if not r:
            self._print(
                "On trunk or no diffs from trunk; no need to look at this.")
            sys.exit(0)

        files = r.strip().split(os.linesep)

        self._print("Looking at these files:")
        for change in files:
            self._print(change)
        self._print("----")

        if len(files) == 1:
            if files[0] == os.sep.join(["docs", "fun", "Twisted.Quotes"]):
                self._print("Quotes change only; no topfile needed.")
                sys.exit(0)

        topfiles = []

        for change in files:
            if os.sep + "topfiles" + os.sep in change:
                if "." in change and change.rsplit(".", 1)[1] in TOPFILE_TYPES:
                    topfiles.append(change)

        if branch.startswith("release-"):
            if topfiles:
                self._print("No topfiles should be on the release branch.")
                sys.exit(1)
            else:
                self._print("Release branch with no topfiles, all good.")
                sys.exit(0)

        for change in topfiles:
            self._print("Found " + change)
            sys.exit(0)

        self._print("No topfile found. Have you committed it?")
        sys.exit(1)
