#!/usr/bin/env python
#
# $Id: setup.py,v 1.1.1.1 2004/07/15 05:24:59 dugsong Exp $

from distutils.core import setup, Extension
import glob, sys

if glob.glob('/usr/lib/libevent.*'):
    print 'found system libevent for', sys.platform
    event = Extension(name='event',
                      sources=[ 'event.c' ],
                      libraries=[ 'event' ])
elif glob.glob('%s/lib/libevent.*' % sys.prefix):
    print 'found installed libevent in', sys.prefix
    event = Extension(name='event',
                      sources=[ 'event.c' ],
                      include_dirs=[ '%s/include' % sys.prefix ],
                      library_dirs=[ '%s/lib' % sys.prefix ],
                      libraries=[ 'event' ])
else:
    l = glob.glob('../libevent*')
    if l:
        libevent_dir = l[0]
        print 'found libevent build directory', libevent_dir
        event = Extension(name='event',
                          sources=[ 'event.c' ],
                          include_dirs = [ libevent_dir ],
                          extra_objects = glob.glob('%s/*.o' % libevent_dir))
    else:
        raise "couldn't find libevent installation or build directory"

setup(name='event',
      version='0.1',
      author='Dug Song, Martin Murray',
      url='http://monkey.org/~dugsong/pyevent',
      description='event library',
      ext_modules = [ event ])
