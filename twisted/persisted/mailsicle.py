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

# system imports
import os
import re

from cStringIO import StringIO

try:
    from new import instance
    from new import instancemethod
except:
    from org.python.core import PyMethod
    instancemethod = PyMethod

# twisted imports
from twisted.python.components import getAdapter, Interface, Adapter, registerAdapter, getAdapterClassWithInheritance
from twisted.python.reflect import qual, namedClass

# reality imports
import popsicle

class IHeaderSaver(Interface):
    """I am an interface which allows objects to be saved to mail-style headers.
    """

    def getItems(self):
        """Get a list of tuples  of strings, [(key, value), ...].
        """

    def getContinuations(self):
        """Get a list of 'continuation' sections. This is a list of lists of tuples.
        """

    def loadItems(self, items, toplevel):
        """Take the result of a getItems() call and populate self.original.
        
        'toplevel' is the top-level object if this is a continuation, otherwise
        it is self.original
        """

    def loadContinuations(self, cont):
        """Take the result of a getContinuations() call and populate self.original.
        """

def writeHeader(f, k, v):
    f.write(k.replace("\\", "\\\\").replace("\n", "\\n").replace(": ", ":\ "))
    f.write(": ")
    f.write(v.replace("\n", "\n\t"))
    f.write("\n")

def parseOIDList(s):
    return re.findall(r'"((?:\\"|.)*?)"(?: (<.*?>))?',s)

def quotify(s):
    return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'

def dictToHeaders(d):
    io = StringIO()
    for k, v in d.items():
        writeHeader(io,k,v)
    return io.getvalue()

wspr = re.compile("\S")

def whitePrefix(s):
    return s[:wspr.search(s).start()]

def getSaver(o):
    return getAdapter(o, IHeaderSaver, adapterClassLocator=getAdapterClassWithInheritance)

class Mailsicle(popsicle.Repository):
    def __init__(self, dirname):
        if not os.path.isdir(dirname):
            os.mkdir(dirname)
        popsicle.Repository.__init__(self)
        self.dirname = dirname

    def loadOID(self, oid):
        f = open(os.path.join(self.dirname, str(oid)))
        llt = f.read().split("\n-\n")
        ll = []
        for lt in llt:
            ll.append(headersToTuples(lt))
        items = ll.pop(0)
        # produce dummy instance
        # ditems = dict(items)
        # OID and Class headers --
        p_oid = items[0][1]
        assert str(oid) == p_oid, "Wrong OID in file."
        cl = reflect.namedClass(ll[1][1])
        # TODO: make instance(...) support new-style classes...
        saver = getSaver(cl)
        saver.loadItems(items)
        saver.loadContinuations(ll)
        return defer.succeed(cl)

    def saveOID(self, oid, obj):
        adapt = getSaver(obj)
        kvl = adapt.getItems()
        f = open(os.path.join(self.dirname, str(oid)), 'w')
        writeHeader(f, "OID", str(oid))
        writeHeader(f, "Class", qual(obj.__class__))
        for key, value in kvl:
            writeHeader(f, key, value)
        for kvl2 in adapt.getContinuations():
            f.write("-\n")
            for key, value in kvl2:
                writeHeader(f, key, value)
