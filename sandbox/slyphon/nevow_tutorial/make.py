#!/usr/bin/env python2.3

from glob import glob
from popen2 import popen4
import sys
import os
import os.path

template = glob('*.tpl')

def lint():
    filelist = glob('*.html')
    for f in filelist:
        print "\n\nlinting %s\n" % f
        oe, i = popen4('/usr/bin/lore -o lint %s' % f)
        for line in oe.readlines():
            sys.stdout.write(line)

def lore():
    clean()
    filelist = glob('*.html')
    for f in filelist:
        print "running lore for %s\n" %f
        oe, i = popen4('/usr/bin/lore --config template=./%s %s' % (template[0], f))
        for line in oe.readlines():
            sys.stdout.write(line)
    make_index_link()

def make_index_link():
    index_link = 'index.html'
    if not os.path.islink(index_link):
        if os.access(index_link, os.F_OK):
            print 'index.html exists and points to: %S' % os.path.realpath('index.html')

        print 'symlinking toc.xhtml to %s' % index_link 
        os.symlink('toc.xhtml', index_link)

def clean():
    print 'cleaning'
    filelist = glob('*.xhtml')
    for f in filelist:
        print 'removing %s' % f
        os.unlink(f)

# webcheck
    
if __name__ == "__main__":
    if sys.argv[1] == 'lint':
        lint()
    if sys.argv[1] == 'lore':
        lore()
    if sys.argv[1] == 'clean':
        clean()
