import sys
from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext
from Pyrex.Compiler import Main

class build_ext(build_ext):

    def pyrex_compile(self, source):
        result = Main.compile(source, Main.CompilationOptions(include_path=["rexactor"]))
        if result.num_errors <> 0:
            sys.exit(1)

setup(
  name = "sample",
  ext_modules=[ 
    Extension("sample", ["sample.pyx"])
    ],
  cmdclass = {'build_ext': build_ext}
)
