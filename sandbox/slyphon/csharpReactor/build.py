#!/usr/bin/python2.3

import os, sys
import os.path as osp
from os.path import join as opj

BIN = "bin/"
IGNORE = ["TwistedServer.cs", "TestTwistedServer.cs", "csharpReactor.cs"]
BUILDDIR = "build"
OUTFILE = "csharpReactor.dll"

def clean():
    dll = opj(BUILDDIR, OUTFILE)
    if osp.exists(dll):
        os.remove(dll)


def build():
    csfiles = []
    libfiles = []
    for dp, dn, fn in os.walk(os.getcwd()):
        if '.svn' in dn:
            dn.remove('.svn')
        for f in fn:
            if f.endswith(".cs") and f not in IGNORE:
                csfiles.append(opj(dp, f))
            if f.endswith(".dll") and f not in IGNORE:
                libfiles.append("-r " + opj(dp, f))

    cmd = ' '.join(["gmcs -g -L lib/ -out:" + opj(BUILDDIR, OUTFILE) + " -target:library -v2 "] + csfiles + libfiles)
    print 'command: %s' % (cmd,)
    os.system(cmd)


if __name__ == '__main__':
    clean()
    build()
