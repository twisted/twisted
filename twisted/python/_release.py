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

from datetime import date
import sys
import os
from tempfile import mkdtemp
import tarfile

from subprocess import PIPE, STDOUT, Popen

from newsbuilder import NewsBuilder

from twisted.python.versions import Version
from twisted.python.filepath import FilePath
from twisted.python.dist import twisted_subprojects
from twisted.python.compat import execfile
from twisted.python.usage import Options, UsageError

# The offset between a year and the corresponding major version number.
VERSION_OFFSET = 2000


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
    Change the version of all projects (including core and all subprojects).

    If the current version of a project is pre-release, then also change the
    versions in the current NEWS entries for that project.

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
    for project in findTwistedProjects(root):
        if project.directory.basename() == "twisted":
            packageName = "twisted"
        else:
            packageName = "twisted." + project.directory.basename()
        oldVersion = project.getVersion()
        newVersion = getNextVersion(oldVersion, prerelease, patch, today)
        if oldVersion.prerelease:
            builder = NewsBuilder()
            builder._changeNewsVersion(
                root.child("NEWS"), builder._getNewsName(project),
                oldVersion, newVersion, formattedToday)
            builder._changeNewsVersion(
                project.directory.child("topfiles").child("NEWS"),
                builder._getNewsName(project), oldVersion, newVersion,
                formattedToday)

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
        self.build(FilePath(args[0]).child("docs"))


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
        """
        if buildDir is None:
            buildDir = docDir.parent().child('doc')

        doctreeDir = buildDir.child('doctrees')

        runCommand(['sphinx-build', '-b', 'html',
                    '-d', doctreeDir.path, docDir.path,
                    buildDir.path])

        for path in docDir.walk():
            if path.basename() == "man":
                segments = path.segmentsFrom(docDir)
                dest = buildDir
                while segments:
                    dest = dest.child(segments.pop(0))
                if not dest.parent().isdir():
                    dest.parent().makedirs()
                path.copyTo(dest)



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
    """
    subprojects = twisted_subprojects

    def __init__(self, rootDirectory, outputDirectory, templatePath=None):
        """
        Create a distribution builder.

        @param rootDirectory: root of a Twisted export which will populate
            subsequent tarballs.
        @type rootDirectory: L{FilePath}.

        @param outputDirectory: The directory in which to create the tarballs.
        @type outputDirectory: L{FilePath}

        @param templatePath: Path to the template file that is used for the
            howto documentation.
        @type templatePath: L{FilePath}
        """
        self.rootDirectory = rootDirectory
        self.outputDirectory = outputDirectory
        self.templatePath = templatePath


    def buildTwisted(self, version):
        """
        Build the main Twisted distribution in C{Twisted-<version>.tar.bz2}.

        bin/admin is excluded.

        @type version: C{str}
        @param version: The version of Twisted to build.

        @return: The tarball file.
        @rtype: L{FilePath}.
        """
        releaseName = "Twisted-%s" % (version,)
        buildPath = lambda *args: '/'.join((releaseName,) + args)

        outputFile = self.outputDirectory.child(releaseName + ".tar.bz2")
        tarball = tarfile.TarFile.open(outputFile.path, 'w:bz2')

        docPath = self.rootDirectory.child("docs")

        # Generate docs!
        if docPath.isdir():
            SphinxBuilder().build(docPath)

        for binthing in self.rootDirectory.child("bin").children():
            # bin/admin should not be included.
            if binthing.basename() != "admin":
                tarball.add(binthing.path,
                            buildPath("bin", binthing.basename()))

        for submodule in self.rootDirectory.child("twisted").children():
            if submodule.basename() == "plugins":
                for plugin in submodule.children():
                    tarball.add(plugin.path, buildPath("twisted", "plugins",
                                                       plugin.basename()))
            else:
                tarball.add(submodule.path, buildPath("twisted",
                                                      submodule.basename()))

        for docDir in self.rootDirectory.child("doc").children():
            if docDir.basename() != "historic":
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
                        if (plugin.basename() ==
                                "twisted_%s.py" % (subproject,)):
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
        return tarball



class UncleanWorkingDirectory(Exception):
    """
    Raised when the working directory of an SVN checkout is unclean.
    """



class NotWorkingDirectory(Exception):
    """
    Raised when a directory does not appear to be an SVN working directory.
    """



def buildAllTarballs(checkout, destination, templatePath=None):
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
    @type templatePath: L{FilePath}
    @param templatePath: Location of the template file that is used for the
        howto documentation.

    @raise UncleanWorkingDirectory: If there are modifications to the
        working directory of C{checkout}.
    @raise NotWorkingDirectory: If the C{checkout} path is not an SVN checkout.
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

    if not destination.exists():
        destination.createDirectory()
    db = DistributionBuilder(export, destination, templatePath=templatePath)

    db.buildCore(versionString)
    for subproject in twisted_subprojects:
        if twistedPath.child(subproject).exists():
            db.buildSubProject(subproject, versionString)

    db.buildTwisted(versionString)
    workPath.remove()



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



class BuildTarballsScript(object):
    """
    A thing for building release tarballs. See L{main}.
    """
    buildAllTarballs = staticmethod(buildAllTarballs)

    def main(self, args):
        """
        Build all release tarballs.

        @type args: list of C{str}
        @param args: The command line arguments to process.  This must contain
            at least two strings: the checkout directory and the destination
            directory. An optional third string can be specified for the
            website template file, used for building the howto documentation.
            If this string isn't specified, the default template included in
            twisted will be used.
        """
        if len(args) < 2 or len(args) > 3:
            sys.exit("Must specify at least two arguments: "
                     "Twisted checkout and destination path. The optional "
                     "third argument is the website template path.")
        if len(args) == 2:
            self.buildAllTarballs(FilePath(args[0]), FilePath(args[1]))
        elif len(args) == 3:
            self.buildAllTarballs(FilePath(args[0]), FilePath(args[1]),
                                  FilePath(args[2]))



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



class BuildNewsOptions(Options):
    """
    Command line parsing for L{BuildNewsScript}.
    """
    synopsis = "build-news [options] REPOSITORY_PATH"
    longdesc = """
    REPOSITORY_PATH: The path to the subversion repository containing the
    topfiles.
    """

    def parseArgs(self, repositoryPath):
        """
        Parse positional arguments.
        """
        self['repositoryPath'] = FilePath(repositoryPath)



class BuildNewsScript(object):
    """
    The entry point for the I{build-news} script.
    """
    def __init__(self, newsBuilder=None, stderr=None):
        """
        @param newsBuilder: A L{NewsBuilder} instance.
        @param stderr: A file to which stderr messages will be written.
        """
        if newsBuilder is None:
            newsBuilder = NewsBuilder()
        self.newsBuilder = newsBuilder

        if stderr is None:
            stderr = sys.stderr
        self.stderr = stderr


    def main(self, args):
        """
        The entry point for the I{build-news} script.
        """
        options = BuildNewsOptions()
        try:
            options.parseOptions(args)
        except UsageError as e:
            message = u'ERROR: {}\n'.format(e.message)
            self.stderr.write(message.encode('utf-8'))
            raise SystemExit(1)

        self.newsBuilder.buildAll(options['repositoryPath'])
