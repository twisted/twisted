from distutils.core import setup, Extension
setup(name="iocpcore",#version="1.0",
      ext_modules=[
          Extension("iocpcore", ["iocpcoreobject.c"],
              libraries=["ws2_32", "mswsock"])
                  ]
     )

