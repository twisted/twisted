#!/usr/bin/env python

# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
        file(f, 'w').write("@%s %s %%1 %%2 %%3 %%4 %%5 %%6 %%7 %%8 %%9" % (pyexe, scriptpy))

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
