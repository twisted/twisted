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

import textwrap
from datetime import date
import re
import sys
import os
from tempfile import mkdtemp
import tarfile

from subprocess import PIPE, STDOUT, Popen

from twisted.python.versions import Version
from twisted.python.filepath import FilePath
from twisted.python.dist import twisted_subprojects

# This import is an example of why you shouldn't use this module unless you're
# radix
try:
    from twisted.lore.scripts import lore
except ImportError:
    pass

# The offset between a year and the corresponding major version number.
VERSION_OFFSET = 2000


# The list of subproject names to exclude from the main Twisted tarball and
# for which no individual project tarballs will be built.
PROJECT_BLACKLIST = ["vfs", "web2"]


def runCommand(args):
    """
    Execute a vector of arguments.

    @type args: C{list} of C{str}
    @param args: A list of arguments, the first of which will be used as the
        executable to run.

    @rtype: C{str}
    @return: All of the standard output.

    @raise CommandFailed: when the program exited with a non-0 exit code.
    """
    process = Popen(args, stdout=PIPE, stderr=STDOUT)
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


def changeAllProjectVersions(root, versionTemplate, today=None):
    """
    Change the version of all projects (including core and all subprojects).

    If the current version of a project is pre-release, then also change the
    versions in the current NEWS entries for that project.

    @type root: L{FilePath}
    @param root: The root of the Twisted source tree.
    @type versionTemplate: L{Version}
    @param versionTemplate: The version of all projects.  The name will be
        replaced for each respective project.
    @type today: C{str}
    @param today: A YYYY-MM-DD formatted string. If not provided, defaults to
        the current day, according to the system clock.
    """
    if not today:
        today = date.today().strftime('%Y-%m-%d')
    for project in findTwistedProjects(root):
        if project.directory.basename() == "twisted":
            packageName = "twisted"
        else:
            packageName = "twisted." + project.directory.basename()
        oldVersion = project.getVersion()
        newVersion = Version(packageName, versionTemplate.major,
                             versionTemplate.minor, versionTemplate.micro,
                             prerelease=versionTemplate.prerelease)

        if oldVersion.prerelease:
            builder = NewsBuilder()
            builder._changeNewsVersion(
                root.child("NEWS"), builder._getNewsName(project),
                oldVersion, newVersion, today)
            builder._changeNewsVersion(
                project.directory.child("topfiles").child("NEWS"),
                builder._getNewsName(project), oldVersion, newVersion,
                today)

        # The placement of the top-level README with respect to other files (eg
        # _version.py) is sufficiently different from the others that we just
        # have to handle it specially.
        if packageName == "twisted":
            _changeVersionInFile(
                oldVersion, newVersion, root.child('README').path)

        project.updateVersion(newVersion)




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
        execfile(self.directory.child("_version.py").path, namespace)
        return namespace["version"]


    def updateVersion(self, version):
        """
        Replace the existing version numbers in _version.py and README files
        with the specified version.
        """
        oldVersion = self.getVersion()
        replaceProjectVersion(self.directory.child("_version.py").path,
                              version)
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
# This is an auto-generated file. Do not edit it.
from twisted.python import versions
version = versions.Version(%r, %s, %s, %s%s)
''' % (version.package, version.major, version.minor, version.micro, prerelease)
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



class LoreBuilderMixin(object):
    """
    Base class for builders which invoke lore.
    """
    def lore(self, arguments):
        """
        Run lore with the given arguments.

        @param arguments: A C{list} of C{str} giving command line arguments to
            lore which should be used.
        """
        options = lore.Options()
        options.parseOptions(["--null"] + arguments)
        lore.runGivenOptions(options)



class DocBuilder(LoreBuilderMixin):
    """
    Generate HTML documentation for projects.
    """

    def build(self, version, resourceDir, docDir, template, apiBaseURL=None,
              deleteInput=False):
        """
        Build the documentation in C{docDir} with Lore.

        Input files ending in .xhtml will be considered. Output will written as
        .html files.

        @param version: the version of the documentation to pass to lore.
        @type version: C{str}

        @param resourceDir: The directory which contains the toplevel index and
            stylesheet file for this section of documentation.
        @type resourceDir: L{twisted.python.filepath.FilePath}

        @param docDir: The directory of the documentation.
        @type docDir: L{twisted.python.filepath.FilePath}

        @param template: The template used to generate the documentation.
        @type template: L{twisted.python.filepath.FilePath}

        @type apiBaseURL: C{str} or C{NoneType}
        @param apiBaseURL: A format string which will be interpolated with the
            fully-qualified Python name for each API link.  For example, to
            generate the Twisted 8.0.0 documentation, pass
            C{"http://twistedmatrix.com/documents/8.0.0/api/%s.html"}.

        @param deleteInput: If True, the input documents will be deleted after
            their output is generated.
        @type deleteInput: C{bool}

        @raise NoDocumentsFound: When there are no .xhtml files in the given
            C{docDir}.
        """
        linkrel = self.getLinkrel(resourceDir, docDir)
        inputFiles = docDir.globChildren("*.xhtml")
        filenames = [x.path for x in inputFiles]
        if not filenames:
            raise NoDocumentsFound("No input documents found in %s" % (docDir,))
        if apiBaseURL is not None:
            arguments = ["--config", "baseurl=" + apiBaseURL]
        else:
            arguments = []
        arguments.extend(["--config", "template=%s" % (template.path,),
                          "--config", "ext=.html",
                          "--config", "version=%s" % (version,),
                          "--linkrel", linkrel] + filenames)
        self.lore(arguments)
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
        @type resourceDir: L{twisted.python.filepath.FilePath}

        @param docDir: The directory containing documents that must link to
            C{resourceDir}.
        @type docDir: L{twisted.python.filepath.FilePath}
        """
        if resourceDir != docDir:
            return '/'.join(filePathDelta(docDir, resourceDir)) + "/"
        else:
            return ""



class ManBuilder(LoreBuilderMixin):
    """
    Generate man pages of the different existing scripts.
    """

    def build(self, manDir):
        """
        Generate Lore input files from the man pages in C{manDir}.

        Input files ending in .1 will be considered. Output will written as
        -man.xhtml files.

        @param manDir: The directory of the man pages.
        @type manDir: L{twisted.python.filepath.FilePath}

        @raise NoDocumentsFound: When there are no .1 files in the given
            C{manDir}.
        """
        inputFiles = manDir.globChildren("*.1")
        filenames = [x.path for x in inputFiles]
        if not filenames:
            raise NoDocumentsFound("No manual pages found in %s" % (manDir,))
        arguments = ["--input", "man",
                     "--output", "lore",
                     "--config", "ext=-man.xhtml"] + filenames
        self.lore(arguments)



class APIBuilder(object):
    """
    Generate API documentation from source files using
    U{pydoctor<http://codespeak.net/~mwh/pydoctor/>}.  This requires
    pydoctor to be installed and usable (which means you won't be able to
    use it with Python 2.3).
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



class BookBuilder(LoreBuilderMixin):
    """
    Generate the LaTeX and PDF documentation.

    The book is built by assembling a number of LaTeX documents.  Only the
    overall document which describes how to assemble the documents is stored
    in LaTeX in the source.  The rest of the documentation is generated from
    Lore input files.  These are primarily XHTML files (of the particular
    Lore subset), but man pages are stored in GROFF format.  BookBuilder
    expects all of its input to be Lore XHTML format, so L{ManBuilder}
    should be invoked first if the man pages are to be included in the
    result (this is determined by the book LaTeX definition file).
    Therefore, a sample usage of BookBuilder may look something like this::

        man = ManBuilder()
        man.build(FilePath("doc/core/man"))
        book = BookBuilder()
        book.build(
            FilePath('doc/core/howto'),
            [FilePath('doc/core/howto'), FilePath('doc/core/howto/tutorial'),
             FilePath('doc/core/man'), FilePath('doc/core/specifications')],
            FilePath('doc/core/howto/book.tex'), FilePath('/tmp/book.pdf'))
    """
    def run(self, command):
        """
        Execute a command in a child process and return the output.

        @type command: C{str}
        @param command: The shell command to run.

        @raise CommandFailed: If the child process exits with an error.
        """
        return runCommand(command)


    def buildTeX(self, howtoDir):
        """
        Build LaTeX files for lore input files in the given directory.

        Input files ending in .xhtml will be considered. Output will written as
        .tex files.

        @type howtoDir: L{FilePath}
        @param howtoDir: A directory containing lore input files.

        @raise ValueError: If C{howtoDir} does not exist.
        """
        if not howtoDir.exists():
            raise ValueError("%r does not exist." % (howtoDir.path,))
        self.lore(
            ["--output", "latex",
             "--config", "section"] +
            [child.path for child in howtoDir.globChildren("*.xhtml")])


    def buildPDF(self, bookPath, inputDirectory, outputPath):
        """
        Build a PDF from the given a LaTeX book document.

        @type bookPath: L{FilePath}
        @param bookPath: The location of a LaTeX document defining a book.

        @type inputDirectory: L{FilePath}
        @param inputDirectory: The directory which the inputs of the book are
            relative to.

        @type outputPath: L{FilePath}
        @param outputPath: The location to which to write the resulting book.
        """
        if not bookPath.basename().endswith(".tex"):
            raise ValueError("Book filename must end with .tex")

        workPath = FilePath(mkdtemp())
        try:
            startDir = os.getcwd()
            try:
                os.chdir(inputDirectory.path)

                texToDVI = [
                    "latex", "-interaction=nonstopmode",
                    "-output-directory=" + workPath.path,
                    bookPath.path]

                # What I tell you three times is true!
                # The first two invocations of latex on the book file allows it
                # correctly create page numbers for in-text references.  Why this is
                # the case, I could not tell you. -exarkun
                for i in range(3):
                    self.run(texToDVI)

                bookBaseWithoutExtension = bookPath.basename()[:-4]
                dviPath = workPath.child(bookBaseWithoutExtension + ".dvi")
                psPath = workPath.child(bookBaseWithoutExtension + ".ps")
                pdfPath = workPath.child(bookBaseWithoutExtension + ".pdf")
                self.run([
                    "dvips", "-o", psPath.path, "-t", "letter", "-Ppdf",
                    dviPath.path])
                self.run(["ps2pdf13", psPath.path, pdfPath.path])
                pdfPath.moveTo(outputPath)
                workPath.remove()
            finally:
                os.chdir(startDir)
        except:
            workPath.moveTo(bookPath.parent().child(workPath.basename()))
            raise


    def build(self, baseDirectory, inputDirectories, bookPath, outputPath):
        """
        Build a PDF book from the given TeX book definition and directories
        containing lore inputs.

        @type baseDirectory: L{FilePath}
        @param baseDirectory: The directory which the inputs of the book are
            relative to.

        @type inputDirectories: C{list} of L{FilePath}
        @param inputDirectories: The paths which contain lore inputs to be
            converted to LaTeX.

        @type bookPath: L{FilePath}
        @param bookPath: The location of a LaTeX document defining a book.

        @type outputPath: L{FilePath}
        @param outputPath: The location to which to write the resulting book.
        """
        for inputDir in inputDirectories:
            self.buildTeX(inputDir)
        self.buildPDF(bookPath, baseDirectory, outputPath)
        for inputDirectory in inputDirectories:
            for child in inputDirectory.children():
                if child.splitext()[1] == ".tex" and child != bookPath:
                    child.remove()



class NewsBuilder(object):
    """
    Generate the new section of a NEWS file.

    The C{_FEATURE}, C{_BUGFIX}, C{_DOC}, C{_REMOVAL}, and C{_MISC}
    attributes of this class are symbolic names for the news entry types
    which are supported.  Conveniently, they each also take on the value of
    the file name extension which indicates a news entry of that type.

    @cvar blacklist: A C{list} of C{str} of projects for which we should not
        generate news at all. Same as C{PROJECT_BLACKLIST}.

    @cvar _headings: A C{dict} mapping one of the news entry types to the
        heading to write out for that type of news entry.

    @cvar _NO_CHANGES: A C{str} giving the text which appears when there are
        no significant changes in a release.

    @cvar _TICKET_HINT: A C{str} giving the text which appears at the top of
        each news file and which should be kept at the top, not shifted down
        with all the other content.  Put another way, this is the text after
        which the new news text is inserted.
    """

    blacklist = PROJECT_BLACKLIST

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
        _MISC: "Other",
        }

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

        Yields C{topfiles}, C{news}, C{name}, C{version} for each sub-project
        in reverse-alphabetical order. C{topfile} is the L{FilePath} for the
        topfiles directory, C{news} is the L{FilePath} for the NEWS file,
        C{name} is the nice name of the project (as should appear in the NEWS
        file), C{version} is the current version string for that project.

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

        for aggregateNews in [False, True]:
            for project in projects:
                if project.directory.basename() in self.blacklist:
                    continue
                topfiles = project.directory.child("topfiles")
                if aggregateNews:
                    news = baseDirectory.child("NEWS")
                else:
                    news = topfiles.child("NEWS")
                name = self._getNewsName(project)
                version = project.getVersion()
                yield topfiles, news, name, version


    def buildAll(self, baseDirectory):
        """
        Find all of the Twisted subprojects beneath C{baseDirectory} and update
        their news files from the ticket change description files in their
        I{topfiles} directories and update the news file in C{baseDirectory}
        with all of the news.

        Projects that are listed in L{NewsBuilder.blacklist} will be skipped.

        @param baseDirectory: A L{FilePath} representing the root directory
            beneath which to find Twisted projects for which to generate
            news (see L{findTwistedProjects}).
        """
        today = self._today()
        for topfiles, news, name, version in self._iterProjects(baseDirectory):
            self.build(
                topfiles, news,
                "Twisted %s %s (%s)" % (name, version.base(), today))


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
            sys.exit("Must specify one argument: the path to the Twisted checkout")
        self.buildAll(FilePath(args[0]))



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



class DistributionBuilder(object):
    """
    A builder of Twisted distributions.

    This knows how to build tarballs for Twisted and all of its subprojects.

    @type blacklist: C{list} of C{str}
    @cvar blacklist: The list of subproject names to exclude from the main
        Twisted tarball and for which no individual project tarballs will be
        built. The same list as C{PROJECT_BLACKLIST}.
    """

    from twisted.python.dist import twisted_subprojects as subprojects
    blacklist = PROJECT_BLACKLIST

    def __init__(self, rootDirectory, outputDirectory, apiBaseURL=None):
        """
        Create a distribution builder.

        @param rootDirectory: root of a Twisted export which will populate
            subsequent tarballs.
        @type rootDirectory: L{FilePath}.

        @param outputDirectory: The directory in which to create the tarballs.
        @type outputDirectory: L{FilePath}

        @type apiBaseURL: C{str} or C{NoneType}
        @param apiBaseURL: A format string which will be interpolated with the
            fully-qualified Python name for each API link.  For example, to
            generate the Twisted 8.0.0 documentation, pass
            C{"http://twistedmatrix.com/documents/8.0.0/api/%s.html"}.
        """
        self.rootDirectory = rootDirectory
        self.outputDirectory = outputDirectory
        self.apiBaseURL = apiBaseURL
        self.manBuilder = ManBuilder()
        self.docBuilder = DocBuilder()


    def _buildDocInDir(self, path, version, howtoPath):
        """
        Generate documentation in the given path, building man pages first if
        necessary and swallowing errors (so that directories without lore
        documentation in them are ignored).

        @param path: The path containing documentation to build.
        @type path: L{FilePath}
        @param version: The version of the project to include in all generated
            pages.
        @type version: C{str}
        @param howtoPath: The "resource path" as L{DocBuilder} describes it.
        @type howtoPath: L{FilePath}
        """
        templatePath = self.rootDirectory.child("doc").child("core"
            ).child("howto").child("template.tpl")
        if path.basename() == "man":
            self.manBuilder.build(path)
        if path.isdir():
            try:
                self.docBuilder.build(version, howtoPath, path,
                    templatePath, self.apiBaseURL, True)
            except NoDocumentsFound:
                pass


    def buildTwisted(self, version):
        """
        Build the main Twisted distribution in C{Twisted-<version>.tar.bz2}.

        Projects listed in in L{blacklist} will not have their plugins, code,
        documentation, or bin directories included.

        bin/admin is also excluded.

        @type version: C{str}
        @param version: The version of Twisted to build.

        @return: The tarball file.
        @rtype: L{FilePath}.
        """
        releaseName = "Twisted-%s" % (version,)
        buildPath = lambda *args: '/'.join((releaseName,) + args)

        outputFile = self.outputDirectory.child(releaseName + ".tar.bz2")
        tarball = tarfile.TarFile.open(outputFile.path, 'w:bz2')

        docPath = self.rootDirectory.child("doc")

        # Generate docs!
        if docPath.isdir():
            for subProjectDir in docPath.children():
                if (subProjectDir.isdir()
                    and subProjectDir.basename() not in self.blacklist):
                    for child in subProjectDir.walk():
                        self._buildDocInDir(child, version,
                            subProjectDir.child("howto"))

        # Now, this part is nasty.  We need to exclude blacklisted subprojects
        # from the main Twisted distribution. This means we need to exclude
        # their bin directories, their documentation directories, their
        # plugins, and their python packages. Given that there's no "add all
        # but exclude these particular paths" functionality in tarfile, we have
        # to walk through all these directories and add things that *aren't*
        # part of the blacklisted projects.

        for binthing in self.rootDirectory.child("bin").children():
            # bin/admin should also not be included.
            if binthing.basename() not in self.blacklist + ["admin"]:
                tarball.add(binthing.path,
                            buildPath("bin", binthing.basename()))

        bad_plugins = ["twisted_%s.py" % (blacklisted,)
                       for blacklisted in self.blacklist]

        for submodule in self.rootDirectory.child("twisted").children():
            if submodule.basename() == "plugins":
                for plugin in submodule.children():
                    if plugin.basename() not in bad_plugins:
                        tarball.add(plugin.path, buildPath("twisted", "plugins",
                                                           plugin.basename()))
            elif submodule.basename() not in self.blacklist:
                tarball.add(submodule.path, buildPath("twisted",
                                                      submodule.basename()))

        for docDir in self.rootDirectory.child("doc").children():
            if docDir.basename() not in self.blacklist:
                tarball.add(docDir.path, buildPath("doc", docDir.basename()))

        for toplevel in self.rootDirectory.children():
            if not toplevel.isdir():
                tarball.add(toplevel.path, buildPath(toplevel.basename()))

        tarball.close()

        return outputFile


    def buildCore(self, version):
        """
        Build a core distribution in C{TwistedCore-<version>.tar.bz2}.

        This is very similar to L{buildSubProject}, but core tarballs and the
        input are laid out slightly differently.

         - scripts are in the top level of the C{bin} directory.
         - code is included directly from the C{twisted} directory, excluding
           subprojects.
         - all plugins except the subproject plugins are included.

        @type version: C{str}
        @param version: The version of Twisted to build.

        @return: The tarball file.
        @rtype: L{FilePath}.
        """
        releaseName = "TwistedCore-%s" % (version,)
        outputFile = self.outputDirectory.child(releaseName + ".tar.bz2")
        buildPath = lambda *args: '/'.join((releaseName,) + args)
        tarball = self._createBasicSubprojectTarball(
            "core", version, outputFile)

        # Include the bin directory for the subproject.
        for path in self.rootDirectory.child("bin").children():
            if not path.isdir():
                tarball.add(path.path, buildPath("bin", path.basename()))

        # Include all files within twisted/ that aren't part of a subproject.
        for path in self.rootDirectory.child("twisted").children():
            if path.basename() == "plugins":
                for plugin in path.children():
                    for subproject in self.subprojects:
                        if plugin.basename() == "twisted_%s.py" % (subproject,):
                            break
                    else:
                        tarball.add(plugin.path,
                                    buildPath("twisted", "plugins",
                                              plugin.basename()))
            elif not path.basename() in self.subprojects + ["topfiles"]:
                tarball.add(path.path, buildPath("twisted", path.basename()))

        tarball.add(self.rootDirectory.child("twisted").child("topfiles").path,
                    releaseName)
        tarball.close()

        return outputFile


    def buildSubProject(self, projectName, version):
        """
        Build a subproject distribution in
        C{Twisted<Projectname>-<version>.tar.bz2}.

        @type projectName: C{str}
        @param projectName: The lowercase name of the subproject to build.
        @type version: C{str}
        @param version: The version of Twisted to build.

        @return: The tarball file.
        @rtype: L{FilePath}.
        """
        releaseName = "Twisted%s-%s" % (projectName.capitalize(), version)
        outputFile = self.outputDirectory.child(releaseName + ".tar.bz2")
        buildPath = lambda *args: '/'.join((releaseName,) + args)
        subProjectDir = self.rootDirectory.child("twisted").child(projectName)

        tarball = self._createBasicSubprojectTarball(projectName, version,
                                                     outputFile)

        tarball.add(subProjectDir.child("topfiles").path, releaseName)

        # Include all files in the subproject package except for topfiles.
        for child in subProjectDir.children():
            name = child.basename()
            if name != "topfiles":
                tarball.add(
                    child.path,
                    buildPath("twisted", projectName, name))

        pluginsDir = self.rootDirectory.child("twisted").child("plugins")
        # Include the plugin for the subproject.
        pluginFileName = "twisted_%s.py" % (projectName,)
        pluginFile = pluginsDir.child(pluginFileName)
        if pluginFile.exists():
            tarball.add(pluginFile.path,
                        buildPath("twisted", "plugins", pluginFileName))

        # Include the bin directory for the subproject.
        binPath = self.rootDirectory.child("bin").child(projectName)
        if binPath.isdir():
            tarball.add(binPath.path, buildPath("bin"))
        tarball.close()

        return outputFile


    def _createBasicSubprojectTarball(self, projectName, version, outputFile):
        """
        Helper method to create and fill a tarball with things common between
        subprojects and core.

        @param projectName: The subproject's name.
        @type projectName: C{str}
        @param version: The version of the release.
        @type version: C{str}
        @param outputFile: The location of the tar file to create.
        @type outputFile: L{FilePath}
        """
        releaseName = "Twisted%s-%s" % (projectName.capitalize(), version)
        buildPath = lambda *args: '/'.join((releaseName,) + args)

        tarball = tarfile.TarFile.open(outputFile.path, 'w:bz2')

        tarball.add(self.rootDirectory.child("LICENSE").path,
                    buildPath("LICENSE"))

        docPath = self.rootDirectory.child("doc").child(projectName)

        if docPath.isdir():
            for child in docPath.walk():
                self._buildDocInDir(child, version, docPath.child("howto"))
            tarball.add(docPath.path, buildPath("doc"))

        return tarball



class UncleanWorkingDirectory(Exception):
    """
    Raised when the working directory of an SVN checkout is unclean.
    """


class NotWorkingDirectory(Exception):
    """
    Raised when a directory does not appear to be an SVN working directory.
    """


def buildAllTarballs(checkout, destination):
    """
    Build complete tarballs (including documentation) for Twisted and all
    subprojects.

    This should be called after the version numbers have been updated and
    NEWS files created.

    @type checkout: L{FilePath}
    @param checkout: The SVN working copy from which a pristine source tree
        will be exported.
    @type destination: L{FilePath}
    @param destination: The directory in which tarballs will be placed.

    @raise UncleanWorkingDirectory: if there are modifications to the
        working directory of C{checkout}.
    @raise NotWorkingDirectory: if the checkout path is not an SVN checkout.
    """
    if not checkout.child(".svn").exists():
        raise NotWorkingDirectory(
            "%s does not appear to be an SVN working directory."
            % (checkout.path,))
    if runCommand(["svn", "st", checkout.path]).strip():
        raise UncleanWorkingDirectory(
            "There are local modifications to the SVN checkout in %s."
             % (checkout.path,))

    workPath = FilePath(mkdtemp())
    export = workPath.child("export")
    runCommand(["svn", "export", checkout.path, export.path])
    twistedPath = export.child("twisted")
    version = Project(twistedPath).getVersion()
    versionString = version.base()

    apiBaseURL = "http://twistedmatrix.com/documents/%s/api/%%s.html" % (
        versionString)
    if not destination.exists():
        destination.createDirectory()
    db = DistributionBuilder(export, destination, apiBaseURL=apiBaseURL)

    db.buildCore(versionString)
    for subproject in twisted_subprojects:
        if (subproject not in db.blacklist
            and twistedPath.child(subproject).exists()):
            db.buildSubProject(subproject, versionString)

    db.buildTwisted(versionString)
    workPath.remove()


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
        version_format = (
            "Version should be in a form kind of like '1.2.3[pre4]'")
        if len(args) != 1:
            sys.exit("Must specify exactly one argument to change-versions")
        version = args[0]
        try:
            major, minor, micro_and_pre = version.split(".")
        except ValueError:
            raise SystemExit(version_format)
        if "pre" in micro_and_pre:
            micro, pre = micro_and_pre.split("pre")
        else:
            micro = micro_and_pre
            pre = None
        try:
            major = int(major)
            minor = int(minor)
            micro = int(micro)
            if pre is not None:
                pre = int(pre)
        except ValueError:
            raise SystemExit(version_format)
        version_template = Version("Whatever",
                                   major, minor, micro, prerelease=pre)
        self.changeAllProjectVersions(FilePath("."), version_template)



class BuildTarballsScript(object):
    """
    A thing for building release tarballs. See L{main}.
    """
    buildAllTarballs = staticmethod(buildAllTarballs)

    def main(self, args):
        """
        Build all release tarballs.

        @type args: list of str
        @param args: The command line arguments to process.  This must contain
            two strings: the checkout directory and the destination directory.
        """
        if len(args) != 2:
            sys.exit("Must specify two arguments: "
                     "Twisted checkout and destination path")
        self.buildAllTarballs(FilePath(args[0]), FilePath(args[1]))



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
