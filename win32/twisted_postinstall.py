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
    install(sitepackages)


def install(sitepackages):
    args=['tkunzip']
    doczip=join(sitepackages, 'twisteddoc.zip')
    docdir=join(sitepackages, 'TwistedDocs')
#    if os.path.isfile(doczip):
#        args.extend(['--zipfile', doczip, '--ziptargetdir', docdir])
    args.extend(['--compiledir', join(sitepackages, 'twisted')])
    tkunzip.run(args)

    if os.path.isfile(doczip):
        tkunzip.run(['tkunzip', '--zipfile', doczip, '--ziptargetdir', docdir])

  

if __name__=='__main__':
    run()
