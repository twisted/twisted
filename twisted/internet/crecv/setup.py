from distutils.core import setup
from distutils.extension import Extension
# pyrex is not available, use existing .c
setup(
    name = 'crecv',
    ext_modules=[
    Extension('crecv', ['crecv.c']),
    ],
)
