# -*- test-case-name: twisted.python.test.test__dist -*-
# Copyright (c) 2010 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Code to support distutils making a distribution of a release.

Much of this code used to live in L{twisted.python._release}, but there is
a distinction between a "distribution" and a "release". Only Twisted devs can
make a release (using the code in C{t.p._release} to build API documentation,
change version numbers, package tarballs and so forth), but anybody anywhere
can use distutils to make a distribution of the files of a particular release.

Because Twisted's release code is only designed to work in a POSIX environment,
it's not appropriate for the generic distutils code to depend on it; therefore
this module contains code for bundling the files of a release into
a distribution, and both C{setup.py} and C{t.p._release} depend on it.
"""

import os, fnmatch, tarfile, errno, shutil
from twisted.lore.scripts import lore


twisted_subprojects = ["conch", "lore", "mail", "names",
                       "news", "pair", "runner", "web", "web2",
                       "words", "vfs"]



# Files and directories matching these patterns will be excluded from Twisted
# releases.
EXCLUDE_PATTERNS = ["{arch}", "_darcs", "*.py[cdo]", "*.s[ol]", ".*", "*~"]



def isDistributable(filepath):
    """
    Determine if the given item should be included in Twisted distributions.

    This function is useful for filtering out files and directories in the
    Twisted directory that aren't supposed to be part of the official Twisted
    package - things like version control system metadata, editor backup files,
    and various other detritus.

    @type filepath: L{FilePath}
    @param filepath: The file or directory that is a candidate for packaging.

    @rtype: C{bool}
    @return: True if the file should be included, False otherwise.
    """
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(filepath.basename(), pattern):
            return False
    return True



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



def _stageFile(src, dest):
    """
    Stages src at the destination path.

    "Staging", in this case, means "creating a temporary copy to be archived".
    In particular, we want to preserve all the metadata of the original file,
    but we don't care about whether edits to the file propagate back and forth
    (since the staged version should never be edited). We hard-link the file if
    we can, otherwise we copy it and preserve metadata.

    @type src: L{twisted.python.filepath.FilePath}
    @param src: The file or path to be staged.

    @type dest: L{twisted.python.filepath.FilePath}
    @param dest: The path at which the source file should be staged. Any
        missing directories in this path will be created.

    @raise OSError: If the source is a file, and the destination already
        exists, C{OSError} will be raised with the C{errno} attribute set to
        C{EEXIST}.
    """

    if not isDistributable(src):
        # Not a file we care about, quietly skip it.
        return

    if src.isfile():
        # Make sure the directory's parent exists.
        destParent = dest.parent()
        if not destParent.exists():
            destParent.makedirs()

        # If the file already exists, raise an exception.
        # os.link raises OSError, shutil.copy (sometimes) raises IOError or
        # overwrites the destination, so let's do the checking ourselves and
        # raise our own error.
        if dest.exists():
            raise OSError(errno.EEXIST, "File exists: %s" % (dest.path,))

        # If we can create a hard link, that's faster than trying to copy
        # things around.
        if hasattr(os, "link"):
            copyfunc = os.link
        else:
            copyfunc = shutil.copy2

        try:
            copyfunc(src.path, dest.path)
        except OSError, e:
            if e.errno == errno.EXDEV:
                shutil.copy2(src.path, dest.path)
            else:
                raise

    elif src.isdir():
        if not dest.exists():
            dest.makedirs()

        for child in src.children():
            _stageFile(child, dest.child(child.basename()))

    else:
        raise NotImplementedError("Can only stage files or directories")



class DistributionBuilder(object):
    """
    A builder of Twisted distributions.

    This knows how to build tarballs for Twisted and all of its subprojects.

    @type blacklist: C{list} of C{str}
    @cvar blacklist: The list subproject names to exclude from the main Twisted
        tarball and for which no individual project tarballs will be built.
    """

    blacklist = ["vfs", "web2"]

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


    def buildTwistedFiles(self, version, releaseName):
        """
        Build a directory containing the main Twisted distribution.
        """
        # Make all the directories we'll need for copying things to.
        distDirectory = self.outputDirectory.child(releaseName)
        distBin = distDirectory.child("bin")
        distTwisted = distDirectory.child("twisted")
        distPlugins = distTwisted.child("plugins")
        distDoc = distDirectory.child("doc")

        for dir in (distDirectory, distBin, distTwisted, distPlugins, distDoc):
            dir.makedirs()

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
                _stageFile(binthing, distBin.child(binthing.basename()))

        bad_plugins = ["twisted_%s.py" % (blacklisted,)
                       for blacklisted in self.blacklist]

        for submodule in self.rootDirectory.child("twisted").children():
            if submodule.basename() == "plugins":
                for plugin in submodule.children():
                    if plugin.basename() not in bad_plugins:
                        _stageFile(plugin,
                                distPlugins.child(plugin.basename()))
            elif submodule.basename() not in self.blacklist:
                _stageFile(submodule, distTwisted.child(submodule.basename()))

        for docDir in self.rootDirectory.child("doc").children():
            if docDir.basename() not in self.blacklist:
                _stageFile(docDir, distDoc.child(docDir.basename()))

        for toplevel in self.rootDirectory.children():
            if not toplevel.isdir():
                _stageFile(toplevel, distDirectory.child(toplevel.basename()))

        # Generate docs in the distribution directory.
        docPath = distDirectory.child("doc")
        if docPath.isdir():
            for subProjectDir in docPath.children():
                if (subProjectDir.isdir()
                    and subProjectDir.basename() not in self.blacklist):
                    for child in subProjectDir.walk():
                        self._buildDocInDir(child, version,
                            subProjectDir.child("howto"))


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

        outputTree = self.outputDirectory.child(releaseName)
        outputFile = self.outputDirectory.child(releaseName + ".tar.bz2")

        tarball = tarfile.TarFile.open(outputFile.path, 'w:bz2')
        self.buildTwistedFiles(version, releaseName)
        tarball.add(outputTree.path, releaseName)
        tarball.close()

        outputTree.remove()

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
                    for subproject in twisted_subprojects:
                        if plugin.basename() == "twisted_%s.py" % (subproject,):
                            break
                    else:
                        tarball.add(plugin.path,
                                    buildPath("twisted", "plugins",
                                              plugin.basename()))
            elif not path.basename() in twisted_subprojects + ["topfiles"]:
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



def makeAPIBaseURL(version):
    """
    Guess where the Twisted API docs for a given version will live.

    @type version: C{str}
    @param version: A URL-safe string containing a version number, such as
        "10.0.0".
    @rtype: C{str}
    @return: A URL template pointing to the Twisted API docs for the given
        version, ready to have the class, module or function name substituted
        in.
    """
    return "http://twistedmatrix.com/documents/%s/api/%%s.html" % (version,)



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



