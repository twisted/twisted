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
from typing import Dict

from zope.interface import Interface, implementer

from subprocess import check_output, STDOUT, CalledProcessError

from twisted.python.compat import execfile
from twisted.python.filepath import FilePath
from twisted.python.monkey import MonkeyPatcher

# Types of newsfragments.
NEWSFRAGMENT_TYPES = ["doc", "bugfix", "misc", "feature", "removal"]
intersphinxURLs = [
    "https://docs.python.org/3/objects.inv",
    "https://cryptography.io/en/latest/objects.inv",
    "https://pyopenssl.readthedocs.io/en/stable/objects.inv",
    "https://hyperlink.readthedocs.io/en/stable/objects.inv",
    "https://twisted.github.io/constantly/docs/objects.inv",
    "https://twisted.github.io/incremental/docs/objects.inv",
    "https://hyper-h2.readthedocs.io/en/stable/objects.inv",
    "https://priority.readthedocs.io/en/stable/objects.inv",
    "https://zopeinterface.readthedocs.io/en/latest/objects.inv",
    "https://automat.readthedocs.io/en/latest/objects.inv",
]


def runCommand(args, **kwargs):
    """Execute a vector of arguments.

    This is a wrapper around L{subprocess.check_output}, so it takes
    the same arguments as L{subprocess.Popen} with one difference: all
    arguments after the vector must be keyword arguments.

    @param args: arguments passed to L{subprocess.check_output}
    @param kwargs: keyword arguments passed to L{subprocess.check_output}
    @return: command output
    @rtype: L{bytes}
    """
    kwargs["stderr"] = STDOUT
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
class GitCommand:
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
                f"{path.path} does not appear to be a Git repository."
            )

    @staticmethod
    def isStatusClean(path):
        """
        Return the Git status of the files in the specified path.

        @type path: L{twisted.python.filepath.FilePath}
        @param path: The path to get the status from (can be a directory or a
            file.)
        """
        status = runCommand(["git", "-C", path.path, "status", "--short"]).strip()
        return status == b""

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
        runCommand(
            [
                "git",
                "-C",
                fromDir.path,
                "checkout-index",
                "--all",
                "--force",
                # prefix has to end up with a "/" so that files get copied
                # to a directory whose name is the prefix.
                "--prefix",
                exportDir.path + "/",
            ]
        )


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

    raise NotWorkingDirectory(f"No supported VCS can be found in {directory.path}")


class Project:
    """
    A representation of a project that has a version.

    @ivar directory: A L{twisted.python.filepath.FilePath} pointing to the base
        directory of a Twisted-style Python package. The package should contain
        a C{_version.py} file and a C{newsfragments} directory that contains a
        C{README} file.
    """

    def __init__(self, directory):
        self.directory = directory

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.directory!r})"

    def getVersion(self):
        """
        @return: A L{incremental.Version} specifying the version number of the
            project based on live python modules.
        """
        namespace: Dict[str, object] = {}
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
        if filePath.basename() == "newsfragments":
            projectDirectory = filePath.parent()
            projects.append(Project(projectDirectory))
    return projects


def replaceInFile(filename, oldToNew):
    """
    I replace the text `oldstr' with `newstr' in `filename' using science.
    """
    os.rename(filename, filename + ".bak")
    with open(filename + ".bak") as f:
        d = f.read()
    for k, v in oldToNew.items():
        d = d.replace(k, v)
    with open(filename + ".new", "w") as f:
        f.write(d)
    os.rename(filename + ".new", filename)
    os.unlink(filename + ".bak")


class NoDocumentsFound(Exception):
    """
    Raised when no input documents are found.
    """


class APIBuilder:
    """
    Generate API documentation from source files using
    U{pydoctor<https://github.com/twisted/pydoctor>}.  This requires
    pydoctor to be installed and usable.
    """

    def build(self, projectName, projectURL, sourceURL, packagePath, outputPath):
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
        from pydoctor.templatewriter import util  # type: ignore[import]

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

        from pydoctor.driver import main  # type: ignore[import]

        args = [
            "--project-name",
            projectName,
            "--project-url",
            projectURL,
            "--system-class",
            "twisted.python._pydoctor.TwistedSystem",
            "--project-base-dir",
            packagePath.parent().path,
            "--html-viewsource-base",
            sourceURL,
            "--html-output",
            outputPath.path,
            "--quiet",
            "--make-html",
        ] + intersphinxes
        args.append(packagePath.path)
        main(args)

        monkeyPatch.restore()


class SphinxBuilder:
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
            sys.stdout.write(f"Unclean build:\n{output}\n")
            raise sys.exit(1)

    def build(self, docDir, buildDir=None, version=""):
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
            buildDir = docDir.parent().child("doc")

        doctreeDir = buildDir.child("doctrees")

        output = runCommand(
            [
                "sphinx-build",
                "-q",
                "-b",
                "html",
                "-d",
                doctreeDir.path,
                docDir.path,
                buildDir.path,
            ]
        ).decode("utf-8")

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


class BuildAPIDocsScript:
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
        sourceURL = (
            "https://github.com/twisted/twisted/tree/"
            "twisted-%s" % (versionString,) + "/src"
        )
        apiBuilder = APIBuilder()
        apiBuilder.build(
            "Twisted",
            "https://twistedmatrix.com/",
            sourceURL,
            projectRoot.child("twisted"),
            output,
        )

    def main(self, args):
        """
        Build API documentation.

        @type args: list of str
        @param args: The command line arguments to process.  This must contain
            two strings: the path to the root of the Twisted checkout, and a
            path to an output directory.
        """
        if len(args) != 2:
            sys.exit(
                "Must specify two arguments: " "Twisted checkout and destination path"
            )
        self.buildAPIDocs(FilePath(args[0]), FilePath(args[1]))


class CheckNewsfragmentScript:
    """
    A thing for checking whether a checkout has a newsfragment.
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

        encoding = sys.stdout.encoding or "ascii"
        location = os.path.abspath(args[0])

        branch = (
            runCommand([b"git", b"rev-parse", b"--abbrev-ref", "HEAD"], cwd=location)
            .decode(encoding)
            .strip()
        )

        # diff-filter=d to exclude deleted newsfiles (which will happen on the
        # release branch)
        r = (
            runCommand(
                [
                    b"git",
                    b"diff",
                    b"--name-only",
                    b"origin/trunk...",
                    b"--diff-filter=d",
                ],
                cwd=location,
            )
            .decode(encoding)
            .strip()
        )

        if not r:
            self._print("On trunk or no diffs from trunk; no need to look at this.")
            sys.exit(0)

        files = r.strip().split(os.linesep)

        self._print("Looking at these files:")
        for change in files:
            self._print(change)
        self._print("----")

        if len(files) == 1:
            if files[0] == os.sep.join(["docs", "fun", "Twisted.Quotes"]):
                self._print("Quotes change only; no newsfragment needed.")
                sys.exit(0)

        newsfragments = []

        for change in files:
            if os.sep + "newsfragments" + os.sep in change:
                if "." in change and change.rsplit(".", 1)[1] in NEWSFRAGMENT_TYPES:
                    newsfragments.append(change)

        if branch.startswith("release-"):
            if newsfragments:
                self._print("No newsfragments should be on the release branch.")
                sys.exit(1)
            else:
                self._print("Release branch with no newsfragments, all good.")
                sys.exit(0)

        for change in newsfragments:
            self._print("Found " + change)
            sys.exit(0)

        self._print("No newsfragment found. Have you committed it?")
        sys.exit(1)
