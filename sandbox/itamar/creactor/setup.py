from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(
  name = "creactor",
  ext_modules=[ 
    Extension("tcp", ["tcp.pyx"]),
    Extension("sample", ["sample.pyx"]),
    ],
  cmdclass = {'build_ext': build_ext}
)
