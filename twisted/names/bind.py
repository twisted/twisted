# -*- test-case-name: twisted.test.test_names -*-
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

"""
Support for creating zone files in the canonical format.

API Stability: Unstable

Future plans: Nicer formatting

@author: U{Jp Calderone<mailto:exarkun@twistedmatrix.com>}
"""

from twisted.protocols import dns

def writeAuthority(soa, records, file=None):
    if not file:
        import sys
        file = sys.stdout

    file.write(soa[0] + ' ' + soa[1].xfrString())
    for host in records.keys():
        file.write(host)
        for r in records[host]:
            if r is not soa[1]:
                file.write('\t' + r.xfrString() + '\n')
