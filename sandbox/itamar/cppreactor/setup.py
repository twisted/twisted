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

setup(
  name = "fusion",
  packages=["fusion"],
  ext_modules=[ 
    Extension("fusion.tcp", [join("fusion", "tcp.cpp")],
              libraries=["boost_python"],
              include_dirs=["include"]),
    Extension("fusion.udp", [join("fusion", "udp.cpp")],
              libraries=["boost_python"],
              include_dirs=["include"]),
    ],
)
