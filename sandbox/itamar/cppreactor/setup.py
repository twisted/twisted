#!/usr/bin/python
import sys, os
from os.path import join
from distutils.core import setup
from distutils.extension import Extension
from distutils import sysconfig

# break abstraction to set g++ as linker - is there better way?
sysconfig._init_posix()
sysconfig._config_vars["CC"] = "g++ -ftemplate-depth-50"
sysconfig._config_vars["LDSHARED"] = "g++ -shared"

ext_modules = []
for name in ["tcp", "udp", "util"]:
    ext_modules.append(Extension("fusion." + name, [join("fusion", "%s.cpp" % name)],
                                 libraries=["boost_python"],
                                 include_dirs=["include"]))

setup(
  name = "fusion",
  packages=["fusion"],
  ext_modules=ext_modules,
)
