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

# post-install

import sys
import os.path
from distutils import sysconfig
import twisted.copyright
from twisted.python import runtime, zipstream, usage
from twisted.scripts import tkunzip
import compileall

def run(argv=sys.argv):
    join=os.path.join
    sitepackages=join(sysconfig.get_config_var('BINLIBDEST'),
                      "site-packages")
    install(sitepackages)



def install(sitepackages):
    # FIXME - make this asynch
    join=os.path.join
    compileall.compile_dir(join(sitepackages, 'twisted'))
    td=join(sitepackages, 'twisteddoc.zip')
    if os.path.isfile(td):
        tkunzip.run(['tkunzip', td, join(sitepackages,'TwistedDocs')])

if __name__=='__main__':
    run()
