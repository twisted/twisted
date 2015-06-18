# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import os
import platform
import sys

from setuptools import Extension, setup as _setup
from setuptools.command import build_ext



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
    for building conditional extensions.

    @param conditionalExtensions: Extensions to optionally build.
    @type conditionalExtensions: C{list} of L{ConditionalExtension}
    """
    return _setup(**get_setup_args(**kw))



def get_setup_args(**kw):

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

        # On Solaris 10, we need to define the _XOPEN_SOURCE and
        # _XOPEN_SOURCE_EXTENDED macros to build in order to gain access to
        # the msg_control, msg_controllen, and msg_flags members in
        # sendmsg.c. (according to
        # http://stackoverflow.com/questions/1034587).  See the documentation
        # of X/Open CAE in the standards(5) man page of Solaris.
        if sys.platform.startswith('sunos'):
            self.define_macros.append(('_XOPEN_SOURCE', 1))
            self.define_macros.append(('_XOPEN_SOURCE_EXTENDED', 1))

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



def _checkCPython(sys=sys, platform=platform):
    """
    Checks if this implementation is CPython.

    This uses C{platform.python_implementation}.

    This takes C{sys} and C{platform} kwargs that by default use the real
    modules. You shouldn't care about these -- they are for testing purposes
    only.

    @return: C{False} if the implementation is definitely not CPython, C{True}
        otherwise.
    """
    return platform.python_implementation() == "CPython"


_isCPython = _checkCPython()
