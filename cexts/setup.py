import os
import sys

if os.path.exists('twistedextensions'):
    sys.path.insert(0, '.') # So we can import twistedextensions


from setuptools import find_packages
from twistedextensions._dist import ConditionalExtension as Extension, setup

extensions = [
    Extension("twistedextensions.raiser",
              ["twistedextensions/raiser.c"],
              condition=lambda _: _isCPython),

    Extension("twistedextensions.iocpsupport",
              ["twistedextensions/iocpsupport/iocpsupport.c",
               "twistedextensions/iocpsupport/winsock_pointers.c"],
              libraries=["ws2_32"],
              condition=lambda _: _isCPython and sys.platform == "win32"),

    Extension("twistedextensions.sendmsg",
              sources=["twistedextensions/sendmsg.c"],
              condition=lambda _: sys.platform != "win32"),
]



__version__ = "1.0.0"


setup(
    name='twistedextensions',
    description='C Extensions for Twisted',
    version=__version__,
    author='Twisted Matrix Laboratories',
    url='https://github.com/twisted/twisted',
    packages=find_packages(),
    license='MIT',
    long_description=file('README.rst').read(),
    ext_modules=extensions
)
