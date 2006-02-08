"""
iovec support
"""
from distutils.core import setup, Extension
if __name__=='__main__':
    setup(
        name='iovec',
        ext_modules=[Extension('iovec', sources=['iovec.c'])],
        py_modules=[],
        version='0.1',
        description='iovec support',
        long_description=__doc__,
        author='Jp Calderone',
        author_email='exarkun@twistedmatrix.com',
        license='GNU LGPL',
        url='http://www.twistedmatrix.com',
        platforms='posix',
        )
