import distutils.sysconfig
distutils.sysconfig.get_config_vars()['LDSHARED'] += ' -framework CoreFoundation -framework CoreServices -framework Carbon'
from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext

setup(
    name = 'cfsupport',
    ext_modules=[
        Extension('cfsupport', ['cfsupport.pyx'], ),
    ],
    cmdclass = {'build_ext': build_ext}
)
