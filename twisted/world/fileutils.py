# -*- test-case-name: twisted.test.test_world -*-
#
# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

import os
opj = os.path.join

from twisted.world import hashless

from twisted.persisted import styles
class WhyCantIHaveWeakReferencesToFilesGoddamnit(file, styles.Ephemeral):
    """My name says it all.
    """

_keepOpenFiles = hashless.HashlessWeakValueDictionary()

def openPlus(*inpath):
    path = opj(*inpath)
    dn = os.path.dirname(path)
    if dn and not os.path.isdir(dn):
        os.makedirs(dn)
    if os.path.exists(path):
        mode = 'rb+'
        #print 'I am quite surprised...', path
    else:
        mode = 'wb+'
    p = os.path.abspath(path)
    if p in _keepOpenFiles and not _keepOpenFiles[p].closed:
        from twisted.python.reflect import objgrep, isSame, findInstances
        # import pdb; pdb.set_trace()
        import sys
        pf = _keepOpenFiles[p]
        # print 'greppage:', '\n'.join(objgrep(sys.modules, pf, isSame))
        print 'fragfiles:', '\n'.join(findInstances(sys.modules, FragmentFile))
##         print gc.get_referrers(pf)
        raise AssertionError("Same file opened twice: %r" % p)
    wciwrtf = WhyCantIHaveWeakReferencesToFilesGoddamnit(path, mode)
    _keepOpenFiles[p] = wciwrtf
    return wciwrtf


class WindowCheckingFile:
    def __init__(self, f, begin, end):
        self.f = f
        self.begin = begin
        self.end = end

    def checktell(self):
        t = self.f.tell()
        assert (t >= self.begin), "%s < %s" % (t, self.begin)
        assert (t <= self.end), "%s > %s" % (t, self.end)

    def close(self):
        raise NotImplementedError("Don't close a file window.")

    def seek(self, offset, whence=0):
        self.f.seek(offset, whence)
        self.checktell()

    def write(self, data):
        self.f.write(data)
        self.checktell()

    def read(self, *args):
        d = self.f.read(*args)
        self.checktell()
        return d

    def tell(self):
        return self.f.tell()
