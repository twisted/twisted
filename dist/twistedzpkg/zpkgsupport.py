import sys, os

from distutils.core import Extension
from distutils.command.build_scripts import build_scripts
from distutils.command.build_ext import build_ext

from distutils.errors import CompileError

from zpkgsetup import dist

class build_scripts_twisted(build_scripts):
    """Renames scripts so they end with '.py' on Windows."""

    def run(self):
        build_scripts.run(self)
        if os.name == "nt":
            for f in os.listdir(self.build_dir):
                fpath=os.path.join(self.build_dir, f)
                if not fpath.endswith(".py"):
                    try:
                        os.unlink(fpath + ".py")
                    except EnvironmentError, e:
                        if e.args[1]=='No such file or directory':
                            pass
                    os.rename(fpath, fpath + ".py")


class build_ext_twisted(build_ext):
    """
    Custom build_ext command simlar to the one in Python2.1/setup.py.
    This allows us to detect (only at build time) what extentions we
    want to build.
    """

    # lame hack! there's an "if not self.extensions" check in
    # build_ext.run. We set it later on to a real list, before
    # actually passing on to build_extensions...
    def run(self):
        self.extensions = True
        build_ext.run(self)

    def build_extensions(self):
        """
        Override the build_ext build_extensions method to call our
        module detection function before it trys to build the extensions.
        """
        self._detect_modules()
        build_ext.build_extensions(self)

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

    def check_define(self, include_files, define_name):
        """
        Check if the given name has been #define'd by trying to compile a
        file that #includes the given files and uses #ifndef to test for the
        name.
        """
        self.compiler.announce("checking for %s..." % define_name, 0)
        return self._compile_helper("""\
%s
#ifndef %s
#error %s is not defined
#endif
""" % ('\n'.join(['#include <%s>' % n for n in include_files]),
       define_name, define_name))

    def check_header(self, header_name):
        """
        Check if the given header can be included by trying to compile a file
        that contains only an #include line.
        """
        self.compiler.announce("checking for %s ..." % header_name, 0)
        return self._compile_helper("#include <%s>\n" % header_name)

    def check_struct_member(self, include_files, struct, member):
        """
        Check that given member is present in the given struct when the
        specified headers are included.
        """
        self.compiler.announce(
            "checking for %s in struct %s..." % (member, struct), 0)
        return self._compile_helper("""\
%s
int main(int argc, char **argv)
{ struct %s foo;  (void)foo.%s;  return(0); }
""" % ('\n'.join(['#include <%s>' % n for n in include_files]), struct, member))
    
    def _detect_modules(self):
        """
        Determine which extension modules we should build on this system.
        """
        # always define WIN32 under Windows
        if os.name == 'nt':
            global_define_macros = [("WIN32", 1)]
        else:
            global_define_macros = []

        print ("Checking if C extensions can be compiled, don't be alarmed if a few compile "
               "errors are printed.")
        
        if not self._compile_helper("#define X 1\n"):
            print "Compiler not found, skipping C extensions."
            return
        
        # Extension modules to build.
        # XXX hack here XXX fdrake will hate me XXX
        from __main__ import context
        extfn = os.path.join(context._working_dir, context._pkgname, 'EXTENSIONS.cfg')
        # end hack (maybe)
        ns = {'builder': self,
              'Extension': Extension}
        execfile(extfn, ns, ns)
        exts = ns['extensions']
        for ext in exts:
            ext.define_macros.extend(global_define_macros)
        self.extensions = exts


class Distribution(dist.ZPkgDistribution):
    def __init__(self, attrs=None):
        dist.ZPkgDistribution.__init__(self, attrs)
        self.cmdclass.setdefault('build_scripts', build_scripts_twisted)
        self.cmdclass.setdefault('build_ext', build_ext_twisted)
        self._mac_osx_hack()

    def has_ext_modules(self):
        # lame hack. see "lame hack" above in build_ext_twisted.
        return True 

    def _mac_osx_hack(self):
        """
        Apple distributes a nasty version of Python 2.2 w/ all release
        builds of OS X 10.2 and OS X Server 10.2
        """

        BROKEN_CONFIG = '2.2 (#1, 07/14/02, 23:25:09) \n[GCC Apple cpp-precomp 6.14]'
        if sys.platform == 'darwin' and sys.version == BROKEN_CONFIG:
            # change this to 1 if you have some need to compile
            # with -flat_namespace as opposed to -bundle_loader
            FLAT_NAMESPACE = 0
            BROKEN_ARCH = '-arch i386'
            BROKEN_NAMESPACE = '-flat_namespace -undefined_suppress'
            import distutils.sysconfig
            distutils.sysconfig.get_config_vars()
            x = distutils.sysconfig._config_vars['LDSHARED']
            y = x.replace(BROKEN_ARCH, '')
            if not FLAT_NAMESPACE:
                e = os.path.realpath(sys.executable)
                y = y.replace(BROKEN_NAMESPACE, '-bundle_loader ' + e)
            if y != x:
                print "Fixing some of Apple's compiler flag mistakes..."
                distutils.sysconfig._config_vars['LDSHARED'] = y

