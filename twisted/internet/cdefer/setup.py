from distutils.core import setup
from distutils.extension import Extension
try:
    from Pyrex.Distutils import build_ext
    # pyrex is available
    setup(
        name = 'cdefer',
        ext_modules=[
            Extension('cdefer', ['cdefer.pyx']),
        ],
        cmdclass = {'build_ext': build_ext}
    )
except ImportError:
    # pyrex is not available, use existing .c
    setup(
        name = 'cdefer',
        ext_modules=[
            Extension('cdefer', ['cdefer.c']),
        ],
    )
