#!/usr/bin/python
from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext
setup(
  name = "PyEvent",
  description = "pyrex wrapper for Niels Provos' libevent library.",
  version = "0.5",
  author = "Martin Murray",
  author_email = "murrayma@citi.umich.edu",
  py_modules = [ "event" ], 
  ext_modules=[
    Extension("libevent", ["libevent.pyx"], libraries = ["event"])
    ],
  cmdclass = {'build_ext': build_ext}
)

