from distutils.core import setup, Extension
setup(name="sendmsg",#version="1.0",
      ext_modules=[Extension("sendmsg", ["sendmsg.c"])])

