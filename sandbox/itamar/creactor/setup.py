from os.path import join
import os
from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

class custom_build_ext(build_ext):
    def pyrex_compile(self, source):
        build_ext.pyrex_compile(self, source)
        if source.endswith("tcp.pyx"):
            os.rename(join("rexactor", "tcp.h"), join("include", "_twisted_tcp.h"))

setup(
  name = "rexactor",
  packages=["rexactor"],
  ext_modules=[ 
    Extension("rexactor.tcp", [join("rexactor", "tcp.pyx")]),
    ],
  cmdclass = {'build_ext': custom_build_ext}
)
