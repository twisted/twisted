
import platform
import sys

from setuptools import Extension, setup as _setup



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
