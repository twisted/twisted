from distutils.core import setup
from distutils.extension import Extension
try:
    from Pyrex.Distutils import build_ext
    # pyrex is available
    setup(
        name = 'cfsupport',
        version = '0.4',
        description = "Enough CoreFoundation wrappers to deal with CFRunLoop",
        long_description = "Pythonic wrappers for pieces of Apple's CoreFoundation API's that are not otherwise wrapped by MacPython.\nPrimarily useful for dealing with CFRunLoop.",
        maintainer = 'Bob Ippolito',
        maintainer_email = 'bob@redivi.com',
        license = 'Python',
        platforms = ['Mac OSX'],
        keywords = ['CoreFoundation', 'CFRunLoop', 'Cocoa', 'GUI'],
        ext_modules=[
            Extension(
                'cfsupport',
                ['cfsupport.pyx'],
                extra_link_args=[
                    '-framework','CoreFoundation',
                    '-framework','CoreServices',
                ],
            ),
        ],
        cmdclass = {'build_ext': build_ext}
    )
except ImportError:
    # pyrex is not available, use existing .c
    setup(
        name = 'cfsupport',
        version = '0.4',
        description = "Enough CoreFoundation wrappers to deal with CFRunLoop",
        long_description = "Pythonic wrappers for pieces of Apple's CoreFoundation API's that are not otherwise wrapped by MacPython.\nPrimarily useful for dealing with CFRunLoop.",
        maintainer = 'Bob Ippolito',
        maintainer_email = 'bob@redivi.com',
        license = 'Python',
        platforms = ['Mac OSX'],
        keywords = ['CoreFoundation', 'CFRunLoop', 'Cocoa', 'GUI'],
        ext_modules=[
            Extension(
                'cfsupport',
                ['cfsupport.c'],
                extra_link_args=[
                    '-framework','CoreFoundation',
                    '-framework','CoreServices',
                ],
            ),
        ],
    )
