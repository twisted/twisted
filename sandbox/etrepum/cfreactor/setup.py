from distutils.core import setup
from distutils.extension import Extension
setup(
    name = 'cfsupport',
    version = '0.3',
    description = 'Enough CoreFoundation wrappers to deal with CFSocket',
    long_description = 'Enough CoreFoundation wrappers to deal with CFSocket',
    maintainer = 'Bob Ippolito',
    maintainer_email = 'bob@redivi.com',
    license = 'MIT',
    platforms = ['Mac OSX'],
    keywords = ['CoreFoundation', 'CFRunLoop', 'CFSocket', 'Cocoa', 'PyObjC'],
    packages = ['cfsupport'],
    ext_modules=[
        Extension(
            'cfsupport._cfsocketmanager',
            ['src/_cfsocketmanager.m'],
            extra_link_args=[
                '-framework','CoreFoundation',
                '-framework','Foundation',
            ],
        ),
    ],
)

