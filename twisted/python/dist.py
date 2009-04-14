"""
Distutils convenience functionality.

Don't use this outside of Twisted.

Maintainer: Christopher Armstrong
"""

import sys, os
from distutils.command import build_scripts, install_data, build_ext, build_py
from distutils.errors import CompileError
from distutils import core
from distutils.core import Extension

twisted_subprojects = ["conch", "lore", "mail", "names",
                       "news", "pair", "runner", "web", "web2",
                       "words", "vfs"]


class ConditionalExtension(Extension):
    """
    An extension module that will only be compiled if certain conditions are
    met.

    @param condition: A callable of one argument which returns True or False to
        indicate whether the extension should be built. The argument is an
        instance of L{build_ext_twisted}, which has useful methods for checking
        things about the platform.
    """
    def __init__(self, *args, **kwargs):
        self.condition = kwargs.pop("condition", lambda builder: True)
        Extension.__init__(self, *args, **kwargs)



def setup(**kw):
    """
    An alternative to distutils' setup() which is specially designed
    for Twisted subprojects.

    Pass twisted_subproject=projname if you want package and data
    files to automatically be found for you.

    @param conditionalExtensions: Extensions to optionally build.
    @type conditionalExtensions: C{list} of L{ConditionalExtension}
    """
    return core.setup(**get_setup_args(**kw))

def get_setup_args(**kw):
    if 'twisted_subproject' in kw:
        if 'twisted' not in os.listdir('.'):
            raise RuntimeError("Sorry, you need to run setup.py from the "
                               "toplevel source directory.")
        projname = kw['twisted_subproject']
        projdir = os.path.join('twisted', projname)

        kw['packages'] = getPackages(projdir, parent='twisted')
        kw['version'] = getVersion(projname)

        plugin = "twisted/plugins/twisted_" + projname + ".py"
        if os.path.exists(plugin):
            kw.setdefault('py_modules', []).append(
                plugin.replace("/", ".")[:-3])

        kw['data_files'] = getDataFiles(projdir, parent='twisted')

        del kw['twisted_subproject']
    else:
        if 'plugins' in kw:
            py_modules = []
            for plg in kw['plugins']:
                py_modules.append("twisted.plugins." + plg)
            kw.setdefault('py_modules', []).extend(py_modules)
            del kw['plugins']

    if 'cmdclass' not in kw:
        kw['cmdclass'] = {
            'install_data': install_data_twisted,
            'build_scripts': build_scripts_twisted}
        if sys.version_info[:3] < (2, 3, 0):
            kw['cmdclass']['build_py'] = build_py_twisted

    if "conditionalExtensions" in kw:
        extensions = kw["conditionalExtensions"]
        del kw["conditionalExtensions"]

        if 'ext_modules' not in kw:
            # This is a workaround for distutils behavior; ext_modules isn't
            # actually used by our custom builder.  distutils deep-down checks
            # to see if there are any ext_modules defined before invoking
            # the build_ext command.  We need to trigger build_ext regardless
            # because it is the thing that does the conditional checks to see
            # if it should build any extensions.  The reason we have to delay
            # the conditional checks until then is that the compiler objects
            # are not yet set up when this code is executed.
            kw["ext_modules"] = extensions

        class my_build_ext(build_ext_twisted):
            conditionalExtensions = extensions
        kw.setdefault('cmdclass', {})['build_ext'] = my_build_ext
    return kw

def getVersion(proj, base="twisted"):
    """
    Extract the version number for a given project.

    @param proj: the name of the project. Examples are "core",
    "conch", "words", "mail".

    @rtype: str
    @returns: The version number of the project, as a string like
    "2.0.0".
    """
    if proj == 'core':
        vfile = os.path.join(base, '_version.py')
    else:
        vfile = os.path.join(base, proj, '_version.py')
    ns = {'__name__': 'Nothing to see here'}
    execfile(vfile, ns)
    return ns['version'].base()


# Names that are exluded from globbing results:
EXCLUDE_NAMES = ["{arch}", "CVS", ".cvsignore", "_darcs",
                 "RCS", "SCCS", ".svn"]
EXCLUDE_PATTERNS = ["*.py[cdo]", "*.s[ol]", ".#*", "*~", "*.py"]

import fnmatch

def _filterNames(names):
    """Given a list of file names, return those names that should be copied.
    """
    names = [n for n in names
             if n not in EXCLUDE_NAMES]
    # This is needed when building a distro from a working
    # copy (likely a checkout) rather than a pristine export:
    for pattern in EXCLUDE_PATTERNS:
        names = [n for n in names
                 if (not fnmatch.fnmatch(n, pattern))
                 and (not n.endswith('.py'))]
    return names

def relativeTo(base, relativee):
    """
    Gets 'relativee' relative to 'basepath'.

    i.e.,

    >>> relativeTo('/home/', '/home/radix/')
    'radix'
    >>> relativeTo('.', '/home/radix/Projects/Twisted') # curdir is /home/radix
    'Projects/Twisted'

    The 'relativee' must be a child of 'basepath'.
    """
    basepath = os.path.abspath(base)
    relativee = os.path.abspath(relativee)
    if relativee.startswith(basepath):
        relative = relativee[len(basepath):]
        if relative.startswith(os.sep):
            relative = relative[1:]
        return os.path.join(base, relative)
    raise ValueError("%s is not a subpath of %s" % (relativee, basepath))


def getDataFiles(dname, ignore=None, parent=None):
    """
    Get all the data files that should be included in this distutils Project.

    'dname' should be the path to the package that you're distributing.

    'ignore' is a list of sub-packages to ignore.  This facilitates
    disparate package hierarchies.  That's a fancy way of saying that
    the 'twisted' package doesn't want to include the 'twisted.conch'
    package, so it will pass ['conch'] as the value.

    'parent' is necessary if you're distributing a subpackage like
    twisted.conch.  'dname' should point to 'twisted/conch' and 'parent'
    should point to 'twisted'.  This ensures that your data_files are
    generated correctly, only using relative paths for the first element
    of the tuple ('twisted/conch/*').
    The default 'parent' is the current working directory.
    """
    parent = parent or "."
    ignore = ignore or []
    result = []
    for directory, subdirectories, filenames in os.walk(dname):
        resultfiles = []
        for exname in EXCLUDE_NAMES:
            if exname in subdirectories:
                subdirectories.remove(exname)
        for ig in ignore:
            if ig in subdirectories:
                subdirectories.remove(ig)
        for filename in _filterNames(filenames):
            resultfiles.append(filename)
        if resultfiles:
            result.append((relativeTo(parent, directory),
                           [relativeTo(parent,
                                       os.path.join(directory, filename))
                            for filename in resultfiles]))
    return result

def getPackages(dname, pkgname=None, results=None, ignore=None, parent=None):
    """
    Get all packages which are under dname. This is necessary for
    Python 2.2's distutils. Pretty similar arguments to getDataFiles,
    including 'parent'.
    """
    parent = parent or ""
    prefix = []
    if parent:
        prefix = [parent]
    bname = os.path.basename(dname)
    ignore = ignore or []
    if bname in ignore:
        return []
    if results is None:
        results = []
    if pkgname is None:
        pkgname = []
    subfiles = os.listdir(dname)
    abssubfiles = [os.path.join(dname, x) for x in subfiles]
    if '__init__.py' in subfiles:
        results.append(prefix + pkgname + [bname])
        for subdir in filter(os.path.isdir, abssubfiles):
            getPackages(subdir, pkgname=pkgname + [bname],
                        results=results, ignore=ignore,
                        parent=parent)
    res = ['.'.join(result) for result in results]
    return res



def getScripts(projname, basedir=''):
    """
    Returns a list of scripts for a Twisted subproject; this works in
    any of an SVN checkout, a project-specific tarball.
    """
    scriptdir = os.path.join(basedir, 'bin', projname)
    if not os.path.isdir(scriptdir):
        # Probably a project-specific tarball, in which case only this
        # project's bins are included in 'bin'
        scriptdir = os.path.join(basedir, 'bin')
        if not os.path.isdir(scriptdir):
            return []
    thingies = os.listdir(scriptdir)
    if '.svn' in thingies:
        thingies.remove('.svn')
    return filter(os.path.isfile,
                  [os.path.join(scriptdir, x) for x in thingies])


## Helpers and distutil tweaks

class build_py_twisted(build_py.build_py):
    """
    Changes behavior in Python 2.2 to support simultaneous specification of
    `packages' and `py_modules'.
    """
    def run(self):
        if self.py_modules:
            self.build_modules()
        if self.packages:
            self.build_packages()
        self.byte_compile(self.get_outputs(include_bytecode=0))



class build_scripts_twisted(build_scripts.build_scripts):
    """Renames scripts so they end with '.py' on Windows."""

    def run(self):
        build_scripts.build_scripts.run(self)
        if not os.name == "nt":
            return
        for f in os.listdir(self.build_dir):
            fpath=os.path.join(self.build_dir, f)
            if not fpath.endswith(".py"):
                try:
                    os.unlink(fpath + ".py")
                except EnvironmentError, e:
                    if e.args[1]=='No such file or directory':
                        pass
                os.rename(fpath, fpath + ".py")



class install_data_twisted(install_data.install_data):
    """I make sure data files are installed in the package directory."""
    def finalize_options(self):
        self.set_undefined_options('install',
            ('install_lib', 'install_dir')
        )
        install_data.install_data.finalize_options(self)



class build_ext_twisted(build_ext.build_ext):
    """
    Allow subclasses to easily detect and customize Extensions to
    build at install-time.
    """

    def prepare_extensions(self):
        """
        Prepare the C{self.extensions} attribute (used by
        L{build_ext.build_ext}) by checking which extensions in
        L{conditionalExtensions} should be built.  In addition, if we are
        building on NT, define the WIN32 macro to 1.
        """
        # always define WIN32 under Windows
        if os.name == 'nt':
            self.define_macros = [("WIN32", 1)]
        else:
            self.define_macros = []
        self.extensions = [x for x in self.conditionalExtensions
                           if x.condition(self)]
        for ext in self.extensions:
            ext.define_macros.extend(self.define_macros)


    def build_extensions(self):
        """
        Check to see which extension modules to build and then build them.
        """
        self.prepare_extensions()
        build_ext.build_ext.build_extensions(self)


    def _remove_conftest(self):
        for filename in ("conftest.c", "conftest.o", "conftest.obj"):
            try:
                os.unlink(filename)
            except EnvironmentError:
                pass


    def _compile_helper(self, content):
        conftest = open("conftest.c", "w")
        try:
            conftest.write(content)
            conftest.close()

            try:
                self.compiler.compile(["conftest.c"], output_dir='')
            except CompileError:
                return False
            return True
        finally:
            self._remove_conftest()


    def _check_header(self, header_name):
        """
        Check if the given header can be included by trying to compile a file
        that contains only an #include line.
        """
        self.compiler.announce("checking for %s ..." % header_name, 0)
        return self._compile_helper("#include <%s>\n" % header_name)

