
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


# System Imports
import types, os, copy, string, cStringIO
if os.sys.platform != 'win32':
    import pwd

# Twisted Imports
from twisted.spread import pb
from twisted.protocols import http
from twisted.internet import tcp
from twisted.python import log
from twisted.persisted import styles

# Sibling Imports
import resource
import server
import error
import html
import static
import widgets
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
        pb.RemoteCopy.setCopyableState(self, state)
        # Emulate the local request interface --
        self.content = cStringIO.StringIO(self.content_data)
        self.write            = self.remote.remoteMethod('write')
        self.finish           = self.remote.remoteMethod('finish')
        self.setHeader        = self.remote.remoteMethod('setHeader')
        self.setResponseCode  = self.remote.remoteMethod('setResponseCode')

    def registerProducer(self, producer, streaming):
        self.remote.callRemote("registerProducer",
                               _ReferenceableProducerWrapper(producer),
                               streaming).addErrback(self.fail)
    def fail(self, failure):
        log.msg(failure.getBriefTraceback())


pb.setCopierForClass(str(server.Request), Request)

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
        """I can't connect to a publisher; I'll now reply to all pending requests.
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
                pb.getObjectAt(self.host, self.port, 10).addCallbacks(self.connected, self.notConnected)

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


class UserDirectory(widgets.Gadget, widgets.StreamWidget):
    userDirName = 'public_html'
    userSocketName = '.twistd-web-pb'

    def stream(self, write, request):
        write('<UL>\n')
        for user in pwd.getpwall():
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = user
            realname = string.split(pw_gecos,',')[0]
            if not realname:
                realname = pw_name
            fmtStr = '<LI><A HREF="%s/">%s (%s)</a>\n'
            if os.path.exists(os.path.join(pw_dir, self.userDirName)):
                write(fmtStr% (pw_name,realname,'file'))
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            if os.path.exists(twistdsock):
                linknm = '%s.twistd' % pw_name
                write(fmtStr% (linknm,realname,'twistd'))
        write('</UL>\n')

    def getWidget(self, chnam, request):
        td = '.twistd'

        if chnam[-len(td):] == td:
            username = chnam[:-len(td)]
            sub = 1
        else:
            username = chnam
            sub = 0
        try:
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = pwd.getpwnam(username)
        except KeyError:
            return error.ErrorPage(http.NOT_FOUND,
                                   "No Such User",
                                   "The user %s was not found on this system." %
                                   repr(username))
        if sub:
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            rs = ResourceSubscription('unix',twistdsock)
            self.putChild(chnam, rs)
            return rs
        else:
            return static.File(os.path.join(pw_dir, self.userDirName))
