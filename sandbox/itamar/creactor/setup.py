from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(
  name = "rexactor",
  packages=["rexactor"],
  ext_modules=[ 
    Extension("rexactor.tcp", ["rexactor/tcp.pyx"]),
    ],
  cmdclass = {'build_ext': build_ext}
)
