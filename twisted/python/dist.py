"""
Distutils convenience functionality.
"""

import sys, os
from distutils import sysconfig
from distutils.command import build_scripts, install_data, build_ext
from distutils.errors import CompileError


# Names that are exluded from globbing results:
EXCLUDE_NAMES = ["{arch}", "CVS", ".cvsignore", "_darcs",
                 "RCS", "SCCS", ".svn"]
EXCLUDE_PATTERNS = ["*.py[cdo]", "*.s[ol]", ".#*", "*~"]

import glob, fnmatch

def _filterNames(names):
    """Given a list of file names, return those names that should be copied.
    """
    names = [n for n in names
             if n not in EXCLUDE_NAMES]
    # This is needed when building a distro from a working
    # copy (likely a checkout) rather than a pristine export:
    for pattern in EXCLUDE_PATTERNS:
        names = [n for n in names
                 if (not fnmatch.fnmatch(n, pattern)) and (not n.endswith('.py'))]
    return names

def getDataFiles(dname):
    result = []
    for directory, subdirectories, filenames in os.walk(dname):
        resultfiles = []
        for exname in EXCLUDE_NAMES:
            if exname in subdirectories:
                subdirectories.remove(exname)
        for filename in _filterNames(filenames):
            resultfiles.append(filename)
        if resultfiles:
            result.append((directory, [os.path.join(directory, filename)
                                       for filename in resultfiles]))
    return result

def getPackages(dname, pkgname=None, results=None):
    bname = os.path.basename(dname)
    if results is None:
        results = []
    if pkgname is None:
        pkgname = []
    subfiles = os.listdir(dname)
    abssubfiles = [os.path.join(dname, x) for x in subfiles]
    if '__init__.py' in subfiles:
        results.append(pkgname + [bname])
        for subdir in filter(os.path.isdir, abssubfiles):
            getPackages(subdir, pkgname + [bname], results)
    return ['.'.join(result) for result in results]

# Apple distributes a nasty version of Python 2.2 w/ all release builds of
# OS X 10.2 and OS X Server 10.2
BROKEN_CONFIG = '2.2 (#1, 07/14/02, 23:25:09) \n[GCC Apple cpp-precomp 6.14]'
if sys.platform == 'darwin' and sys.version == BROKEN_CONFIG:
    # change this to 1 if you have some need to compile
    # with -flat_namespace as opposed to -bundle_loader
    FLAT_NAMESPACE = 0
    BROKEN_ARCH = '-arch i386'
    BROKEN_NAMESPACE = '-flat_namespace -undefined_suppress'
    sysconfig.get_config_vars()
    x = sysconfig._config_vars['LDSHARED']
    y = x.replace(BROKEN_ARCH, '')
    if not FLAT_NAMESPACE:
        e = os.path.realpath(sys.executable)
        y = y.replace(BROKEN_NAMESPACE, '-bundle_loader ' + e)
    if y != x:
        print "Fixing some of Apple's compiler flag mistakes..."
        sysconfig._config_vars['LDSHARED'] = y

## Helpers and distutil tweaks

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
    def build_extensions(self):
        """
        Override the build_ext build_extensions method to call our
        module detection function before it trys to build the extensions.
        """
        self.extensions = []
        self._detect_modules()
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

