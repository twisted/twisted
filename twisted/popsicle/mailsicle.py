# -*- test-case-name: twisted.test.test_popsicle -*-
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

"""

Mailsicle

A Reference Implementation of a Popsicle Back-End.

This is a very simple persistence mechanism that demonstrates various things
about the Popsicle persistence manager.  It is very slow and its scalability
depends intimately on the performance characteristics of your filesystem, so
use with caution.

There are a few advantages to using Mailsicle for persistence, however.  Its
fileformat is almost completely transparent: it uses an RFC822-inspired (though
by no means compliant!) fileformat for easy inspection and manual repair.  It
provides very basic indexes, which is a slight advantage over dirdbm+shelf
persistence.

One slightly strange advantage is that it's somewhat tedious to write
persistence adapters for mailsicle.  This provides a useful exercise in
locating the essential information that you want to persist, and can be a
useful prelude to developing an efficient relational schema for a set of
objects, while providing a fallback mechanism in the case where a database is
not installed.

Future Work:

    - optionally allow for backending to BSDDB or other single-file approach
      instead of sprawling across filesystem, first for indexes, then for
      content

"""

# system imports
import os
import re
import weakref

from cStringIO import StringIO

# twisted imports
from twisted.python.components import getAdapter, Interface, Adapter, registerAdapter, getAdapterClassWithInheritance
from twisted.python.reflect import qual, namedClass
from twisted.python.compat import dict
from twisted.internet import defer

# sibling imports
from twisted.popsicle import repos, freezer


class IHeaderSaver(Interface):
    """I am an interface which allows objects to be saved to mail-style headers.
    """

    def descriptiveName(self):
        """Return a pretty-printed (non-unique) name describing me.
        """

    def getItems(self):
        """Get a list of tuples  of strings, [(key, value), ...].
        """

    def getIndexes(self):
        """Return a list of tuples of strings, [(index_name, index_value), ...]
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

psl = r'"((?:\"|.)*?)"'
poidl = r'(?:%s |)<([^>]*)>' % psl

psl = re.compile(psl)
poidl = re.compile(poidl)


def parseOIDList(s):
    return poidl.findall(s)

def parseStringList(s):
    return psl.findall(s)

def makeStringList(l):
    return ', '.join(map(quotify, l))

def quotify(s):
    return '"'+s.replace('\\','\\\\').replace('"','\\"')+'"'

def dictToHeaders(d):
    io = StringIO()
    for k, v in d.items():
        writeHeader(io,k,v)
    return io.getvalue()

def headersToTuples(hdrs):
    hdrl = []
    protohdr = None
    for line in hdrs.split("\n"):
        if not line: continue
        if line[0] != '\t':
            header, valBegin = line.split(': ', 1)
            if protohdr:
                hdrl.append(tuple(protohdr))
            protohdr = [header, valBegin]
        else:
            protohdr[1] += '\n'+line[1:]
    if protohdr:
        hdrl.append(tuple(protohdr))
    return hdrl

wspr = re.compile("\S")

def whitePrefix(s):
    return s[:wspr.search(s).start()]

def getSaver(o,repo):
    adapt = getAdapter(o, IHeaderSaver, adapterClassLocator=getAdapterClassWithInheritance)
    adapt.repo = repo
    return adapt

class QueryResults:
    def __init__(self, oidlist, repo):
        self.oidlist = oidlist
        self.repo = repo

    def fetch(self, begin=0, end=None):
        return defer.execute(self.fetchNow, begin, end)

    def fetchNow(self, begin=0, end=None):
        if end is None:
            end = len(self.oidlist)
        entries = self.oidlist[begin:end]
        return map(self.repo.loadNow, entries)


class Mailsicle(repos.DirectoryRepository):

    def loadOIDNow(self, oid):
        try:
            f = open(os.path.join(self.dirname, str(oid)))
        except (OSError, IOError):
            raise repos.OIDNotFound(str(oid))
        
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
        cl = self.createOID(oid, namedClass(items[1][1]))
        # TODO: make instance(...) support new-style classes...
        saver = getSaver(cl,self)
        saver.loadItems(items, cl)
        saver.loadContinuations(ll)
        return cl

    def cache(self, oid, obj, finished=1):
        if finished:
            idxs = getSaver(obj,self).getIndexes()
        else:
            idxs = []
        self._cache[oid] = obj
        self._revCache[obj] = [oid, idxs]

    def getOldIndexes(self, obj):
        if self._revCache.has_key(obj):
            return self._revCache[obj][1]
        return []

    def getOID(self, obj):
        if self._revCache.has_key(obj):
            return self._revCache[obj][0]
        else:
            # TODO: if OID generation really needs to be async...
            return freezer.ref(obj).acquireOID(self)

    def saveOID(self, oid, obj):
        adapt = getSaver(obj,self)
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
        idxs = dict(self.getOldIndexes(obj))
        nidxs = adapt.getIndexes()
        for idx, value in nidxs:
            # store all new indexes
            if idxs.has_key(idx):
                # if I had it before, update it
                if idxs[idx] != value:
                    # print 'updating index',oid,idx,idxs[idx],'=>',value
                    self.removeIndex(oid, idx, idxs[idx])
                    self.storeIndex(oid, idx, value)
                # track it's been removed
                del idxs[idx]
            else:
                # print 'storing new index',oid,idx,'=>',value
                self.storeIndex(oid, idx, value)
        for idx, value in idxs.items():
            # clear all remaining indexes
            # print 'clearing old index',oid,idx,'=>',value
            self.removeIndex(oid, idx, value)

    def storeIndex(self, oid, idx, value):
        # print 'indexing',oid,idx,value
        oid = str(oid)
        idxd = "index-"+idx
        opj = os.path.join
        dirn = opj(self.dirname, idxd, value)
        if not os.path.isdir(dirn):
            os.makedirs(dirn)
        os.symlink(opj('..','..', oid),
                   opj(self.dirname, idxd, value, oid))

    def removeIndex(self, oid, idx, value):
        # print 'deindexing', oid, idx, value
        oid = str(oid)
        idxd = "index-"+idx
        opj = os.path.join
        dirn = opj(self.dirname, idxd, value)
        if not os.path.isdir(dirn):
            return
        if not os.path.islink(opj(dirn, oid)):
            return
        os.unlink(opj(dirn,oid))

    def queryIndex(self, idx, value):
        opj = os.path.join
        idxd = "index-" + idx
        try:
            entries = os.listdir(opj(self.dirname, idxd, value))
        except OSError:
            return QueryResults([], self)
        return QueryResults(entries, self)

    def loadOIDList(self, s):
        l = []
        for descript, oid in parseOIDList(s):
            l.append(self.loadNow(oid))
        return l

    def makeOIDList(self,l):
        return ', '.join(map(self.addressOID, l))

    def addressOID(self, obj, desc=None):
        if obj is not None:
            oid = freezer.ref(obj, self).acquireOID()
            if desc is not None:
                return '%s <%s>' % (quotify(desc), oid)
            else:
                if desc=='':
                    return '<%s>' % oid
                else:
                    return ('%s <%s>' %
                            (quotify(getSaver(obj,self).descriptiveName()),
                             oid))
        else:
            return '<>'


from twisted.cred import service, authorizer, identity, perspective

def hexlify(s):
    # note: when we drop 2.1 support, we can just
    #  s.encode('hex') and s.decode('hex')
    return ''.join(['%02x' % ord(c) for c in s])

def unhexlify(s):
    return ''.join([chr(int(s[i:i+2],16)) for i in range(0,len(s),2)])

class DefaultSaver(Adapter):
    __implements__ = IHeaderSaver

    def descriptiveName(self):
        """Return a pretty-printed (non-unique) name describing me.
        """
        if hasattr(self.original, "name"):
            return self.original.name

    def getItems(self):
        """Get a list of tuples  of strings, [(key, value), ...].
        """
        return []

    def getContinuations(self):
        """Get a list of 'continuation' sections. This is a list of lists of tuples.
        """
        return []

    def getIndexes(self):
        """
        """
        return []

    def loaditem_oid(self, kv, vv):
        pass

    def loaditem_class(self, kv, vv):
        pass

    def preLoad(self):
        pass

    def postLoad(self):
        pass

    def loadItems(self, items, toplevel):
        """Take the result of a getItems() call and populate self.original.
        
        'toplevel' is the top-level object if this is a continuation, otherwise
        it is self.original
        """
        self.preLoad()
        for k,v in items:
            ksplit = k.split("+", 1)
            kk = ksplit[0]
            if len(ksplit) > 1:
                kv = ksplit[1]
            else:
                kv = None
            getattr(self,"loaditem_"+kk.lower())(kv,v)
        self.postLoad()

    def loadContinuations(self, cont):
        """Take the result of a getContinuations() call and populate self.original.
        """

class IdentitySaver(DefaultSaver):
    '''Persistor for cred Identities.
    '''
    def getItems(self):
        itm = [("Name", self.original.name),
               ("Password", hexlify(self.original.hashedPassword))]
        for svcnam, pspnam in self.original.keyring.keys():
            itm.append(("Key+"+svcnam, pspnam))
        return itm

    def preLoad(self):
        # XXX currently I want authorizers to be in a weird halfway-in
        # relationship with the database, so this is necessary to keep
        # identities in sync
        self.original.authorizer = self.repo._authorizer
        self.original.keyring = {}

    def loaditem_key(self, kv, vv):
        self.original.keyring[(kv,vv)] = 1

    def loaditem_password(self, kv, vv):
        self.original.hashedPassword = unhexlify(vv)

    def loaditem_name(self, kv, vv):
        self.original.name = vv

    def getIndexes(self):
        return [("identity-name", self.original.name)]

registerAdapter(IdentitySaver, identity.Identity, IHeaderSaver)

class PerspectiveSaver(DefaultSaver):
    def getItems(self):
        return [('Service', self.original.getService().serviceName),
                ('Name', self.original.perspectiveName)]

    def getIndexes(self):
        return [("perspective-name-"+self.original.service.serviceName,
                 self.original.perspectiveName)]

    def loaditem_service(self, kv, vv):
        self.original.service = self.repo._services[vv]

    def loaditem_name(self, kv, vv):
        self.original.perspectiveName = vv

registerAdapter(PerspectiveSaver, perspective.Perspective, IHeaderSaver)

class MailsicleAuthorizer(authorizer.Authorizer):
    """A twisted.cred authorizer that's persistent in a Mailsicle database.
    
    NOTE: only one MailsicleAuthorizer may be present in a given Mailsicle
    database.
    """
    def __init__(self, msicle, serviceCollection=None):
        if hasattr(msicle, "_authorizer"):
            raise NotImplementedError("Only one authorizer "
                                      "per mailsicle allowed.")
        authorizer.Authorizer.__init__(self, serviceCollection)
        self.msicle = msicle
        self.msicle._authorizer = self

    def addIdentity(self, identity):
        freezer.register(identity, self.msicle)

    ## XXX TODO: removeIdentity

    def getIdentityRequest(self, name):
        return self.msicle.queryIndex("identity-name",
                                      name).fetch(0,1).addCallback(lambda x: x[0])



class MailsicleService(service.Service):
    """A twisted.cred service that's persistent in a Mailsicle database.

    NOTE: such services must have a unique serviceName for the mailsicle they
    are persistent in.  There is currently no checking.

    TODO: this should be generalized to load Perspectives from any data-source
    that implements a certain Repository interface.
    """

    def __init__(self, msicle, serviceName, serviceParent=None, authorizer=None):
        service.Service.__init__(self, serviceName, serviceParent, authorizer)
        self.msicle = msicle
        # XXX FIXME: same as in IdentitySaver.loadItems
        if not hasattr(self.msicle, '_services'):
            self.msicle._services = {}
        self.msicle._services[serviceName] = self
        self.perspectives = weakref.WeakValueDictionary()

    def __getstate__(self):
        dct = self.__dict__.copy()
        del dct['perspectives']

    def __setstate__(self, dct):
        self.__dict__ = dct
        self.perspectives = weakref.WeakValueDictionary()


    def stopService(self):
        freezer.clean()

    def createPerspective(self, name):
        p = self.perspectiveClass(name)
        p.setService(self)
        freezer.register(p, self.msicle)
        self.perspectives[name] = p
        return p

    def getPerspectiveNamed(self, name):
        if self.perspectives.has_key(name):
            return self.perspectives[name]
        l = self.msicle.queryIndex("perspective-name-"+self.serviceName,
                                      name).fetchNow(0,1)
        try:
            return l[0]
        except IndexError:
            raise KeyError("%s doesn't exist." % name)

