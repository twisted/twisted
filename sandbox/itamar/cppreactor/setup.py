#!/usr/bin/python
import sys, os
from os.path import join
from distutils.core import setup
from distutils.extension import Extension
from distutils import sysconfig

# break abstraction to set g++ as linker - is there better way?
sysconfig._init_posix()
compiler = "g++ -ftemplate-depth-50"
#compiler += " -fkeep-inline-functions" # for debugging

# workaround for bugs in Redhat 7.3 compiler
if os.popen("g++ --version").read().strip() == "2.96":
    compiler += " -fno-inline "

sysconfig._config_vars["CC"] = compiler
sysconfig._config_vars["LDSHARED"] = "g++ -shared"

ext_modules = []
include_dirs = ["./include", "/usr/local/include"]
if os.environ.has_key("BOOST_INCLUDE"):
    include_dirs.append(os.environ["BOOST_INCLUDE"])

libraries = []
for libpath in (os.environ.get("LD_LIBRARY_PATH", "").split(":") + ["/usr/lib", "/lib", "/usr/local/lib"]):
    if os.path.exists(os.path.join(libpath, "libboost_python.so")):
        libraries.append("boost_python")
        break
else:
    libraries.append("boost_python-gcc-mt")



ext_modules.append(Extension("fusion._fusion", [join("fusion", "%s.cpp" % name) for name in
                                                ("tcp", "udp", "util", "_fusion")],
                             libraries=libraries,
                             library_dirs=["/usr/local/lib"],
                             include_dirs=include_dirs))

setup(
  name = "fusion",
  packages=["fusion"],
  ext_modules=ext_modules,
)
