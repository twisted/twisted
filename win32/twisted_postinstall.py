#!/usr/bin/env python

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


import sys
import os.path
join=os.path.join
from distutils import sysconfig
from twisted.scripts import tkunzip

def run(argv=sys.argv):
    sitepackages=join(sysconfig.get_config_var('BINLIBDEST'),
                      "site-packages")
    prefix=sysconfig.get_config_var('prefix')
    install(sitepackages, prefix)


def install(sitepackages, prefix):
    # bat files for pys so twisted command prompt works
    scripts=join(prefix, 'scripts')
    pyexe=join(prefix, 'python.exe')
    for bat in """twistd.bat mktap.bat websetroot.bat lore.bat 
               manhole.bat tapconvert.bat trial.bat coil.bat""".split():
        f=join(scripts, bat)
        scriptpy=f.replace('.bat', '.py')
        file(f, 'w').write("@%s %s %%*" % (pyexe, scriptpy))

    args=['tkunzip']
    doczip=join(sitepackages, 'twisteddoc.zip')
    docdir=join(sitepackages, 'TwistedDocs')
    # FIXME - should be able to do it this way (one invocation)
#    if os.path.isfile(doczip):
#        args.extend(['--zipfile', doczip, '--ziptargetdir', docdir])
    args.extend(['--compiledir', join(sitepackages, 'twisted'),])
    tkunzip.run(args)

    if os.path.isfile(doczip):
        tkunzip.run(['tkunzip', '--zipfile', doczip, '--ziptargetdir',
                     docdir,])


if __name__=='__main__':
    run()
