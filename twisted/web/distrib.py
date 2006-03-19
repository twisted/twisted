# -*- test-case-name: twisted.web.test.test_web -*-

# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""Distributed web servers.

This is going to have to be refactored so that argument parsing is done
by each subprocess and not by the main web server (i.e. GET, POST etc.).
"""

# System Imports
import types, os, copy, string, cStringIO
if (os.sys.platform != 'win32') and (os.name != 'java'):
    import pwd

# Twisted Imports
from twisted.spread import pb
from twisted.web import http
from twisted.python import log
from twisted.persisted import styles
from twisted.web.woven import page
from twisted.internet import address, reactor

# Sibling Imports
import resource
import server
import error
import html
import static
from server import NOT_DONE_YET

class _ReferenceableProducerWrapper(pb.Referenceable):
    def __init__(self, producer):
        self.producer = producer

    def remote_resumeProducing(self):
        self.producer.resumeProducing()

    def remote_pauseProducing(self):
        self.producer.pauseProducing()

    def remote_stopProducing(self):
        self.producer.stopProducing()


class Request(pb.RemoteCopy, server.Request):
    def setCopyableState(self, state):
        for k in 'host', 'client':
            tup = state[k]
            addrdesc = {'INET': 'TCP', 'UNIX': 'UNIX'}[tup[0]]
            addr = {'TCP': lambda: address.IPv4Address(addrdesc,
                                                       tup[1], tup[2],
                                                       _bwHack='INET'),
                    'UNIX': lambda: address.UNIXAddress(tup[1])}[addrdesc]()
            state[k] = addr
        pb.RemoteCopy.setCopyableState(self, state)
        # Emulate the local request interface --
        self.content = cStringIO.StringIO(self.content_data)
        self.write            = self.remote.remoteMethod('write')
        self.finish           = self.remote.remoteMethod('finish')
        self.setHeader        = self.remote.remoteMethod('setHeader')
        self.addCookie        = self.remote.remoteMethod('addCookie')
        self.setETag          = self.remote.remoteMethod('setETag')
        self.setResponseCode  = self.remote.remoteMethod('setResponseCode')
        self.setLastModified  = self.remote.remoteMethod('setLastModified')

    def registerProducer(self, producer, streaming):
        self.remote.callRemote("registerProducer",
                               _ReferenceableProducerWrapper(producer),
                               streaming).addErrback(self.fail)

    def unregisterProducer(self):
        self.remote.callRemote("unregisterProducer").addErrback(self.fail)

    def fail(self, failure):
        log.err(failure)


pb.setCopierForClass(server.Request, Request)

class Issue:
    def __init__(self, request):
        self.request = request

    def finished(self, result):
        if result != NOT_DONE_YET:
            assert isinstance(result, types.StringType),\
                   "return value not a string"
            self.request.write(result)
            self.request.finish()

    def failed(self, failure):
        #XXX: Argh. FIXME.
        failure = str(failure)
        self.request.write(
            error.ErrorPage(http.INTERNAL_SERVER_ERROR,
                            "Server Connection Lost",
                            "Connection to distributed server lost:" +
                            html.PRE(failure)).
            render(self.request))
        self.request.finish()
        log.msg(failure)


class ResourceSubscription(resource.Resource):
    isLeaf = 1
    waiting = 0
    def __init__(self, host, port):
        resource.Resource.__init__(self)
        self.host = host
        self.port = port
        self.pending = []
        self.publisher = None

    def __getstate__(self):
        """Get persistent state for this ResourceSubscription.
        """
        # When I unserialize,
        state = copy.copy(self.__dict__)
        # Publisher won't be connected...
        state['publisher'] = None
        # I won't be making a connection
        state['waiting'] = 0
        # There will be no pending requests.
        state['pending'] = []
        return state

    def connected(self, publisher):
        """I've connected to a publisher; I'll now send all my requests.
        """
        log.msg('connected to publisher')
        publisher.broker.notifyOnDisconnect(self.booted)
        self.publisher = publisher
        self.waiting = 0
        for request in self.pending:
            self.render(request)
        self.pending = []

    def notConnected(self, msg):
        """I can't connect to a publisher; I'll now reply to all pending
        requests.
        """
        log.msg("could not connect to distributed web service: %s" % msg)
        self.waiting = 0
        self.publisher = None
        for request in self.pending:
            request.write("Unable to connect to distributed server.")
            request.finish()
        self.pending = []

    def booted(self):
        self.notConnected("connection dropped")

    def render(self, request):
        """Render this request, from my server.

        This will always be asynchronous, and therefore return NOT_DONE_YET.
        It spins off a request to the pb client, and either adds it to the list
        of pending issues or requests it immediately, depending on if the
        client is already connected.
        """
        if not self.publisher:
            self.pending.append(request)
            if not self.waiting:
                self.waiting = 1
                bf = pb.PBClientFactory()
                timeout = 10
                if self.host == "unix":
                    reactor.connectUNIX(self.port, bf, timeout)
                else:
                    reactor.connectTCP(self.host, self.port, bf, timeout)
                d = bf.getRootObject()
                d.addCallbacks(self.connected, self.notConnected)

        else:
            i = Issue(request)
            self.publisher.callRemote('request', request).addCallbacks(i.finished, i.failed)
        return NOT_DONE_YET

class ResourcePublisher(pb.Root, styles.Versioned):
    def __init__(self, site):
        self.site = site

    persistenceVersion = 2

    def upgradeToVersion2(self):
        self.application.authorizer.removeIdentity("web")
        del self.application.services[self.serviceName]
        del self.serviceName
        del self.application
        del self.perspectiveName

    def getPerspectiveNamed(self, name):
        return self

    def remote_request(self, request):
        res = self.site.getResourceFor(request)
        log.msg( request )
        return res.render(request)

class UserDirectory(page.Page):
    userDirName = 'public_html'
    userSocketName = '.twistd-web-pb'

    template = """
<html>
    <head>
    <title>twisted.web.distrib.UserDirectory</title>
    <style>
    
    a
    {
        font-family: Lucida, Verdana, Helvetica, Arial, sans-serif;
        color: #369;
        text-decoration: none;
    }

    th
    {
        font-family: Lucida, Verdana, Helvetica, Arial, sans-serif;
        font-weight: bold;
        text-decoration: none;
        text-align: left;
    }

    pre, code
    {
        font-family: "Courier New", Courier, monospace;
    }

    p, body, td, ol, ul, menu, blockquote, div
    {
        font-family: Lucida, Verdana, Helvetica, Arial, sans-serif;
        color: #000;
    }
    
    </style>
    <base view="Attributes" model="base" />
    </head>

    <body>
    <h1>twisted.web.distrib.UserDirectory</h1>

    <ul view="List" model="directory">
            <li pattern="listItem"><a view="Link" /> </li>
    </ul>
</body>
</html>
    """

    def wmfactory_base(self, request):
        return {'href':request.prePathURL()}

    def wmfactory_directory(self, request):
        m = []
        for user in pwd.getpwall():
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = user
            realname = string.split(pw_gecos,',')[0]
            if not realname:
                realname = pw_name
            if os.path.exists(os.path.join(pw_dir, self.userDirName)):
                m.append({
                        'href':'%s/'%pw_name,
                        'text':'%s (file)'%realname
                })
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            if os.path.exists(twistdsock):
                linknm = '%s.twistd' % pw_name
                m.append({
                        'href':'%s/'%linknm,
                        'text':'%s (twistd)'%realname})
        return m

    def getChild(self, name, request):
        if name == '':
            return self

        td = '.twistd'

        if name[-len(td):] == td:
            username = name[:-len(td)]
            sub = 1
        else:
            username = name
            sub = 0
        try:
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = pwd.getpwnam(username)
        except KeyError:
            return error.NoResource()
        if sub:
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            rs = ResourceSubscription('unix',twistdsock)
            self.putChild(name, rs)
            return rs
        else:
            path = os.path.join(pw_dir, self.userDirName)
            if not os.path.exists(path):
                return error.NoResource()
            return static.File(path)
