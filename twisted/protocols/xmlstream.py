# -*- test-case-name: twisted.test.test_xmlstream -*-
#
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

from twisted.internet import reactor, protocol, defer
from twisted.xish import domish, utility

STREAM_CONNECTED_EVENT = intern("//event/stream/connected")
STREAM_START_EVENT = intern("//event/stream/start")
STREAM_END_EVENT = intern("//event/stream/end")
STREAM_ERROR_EVENT = intern("//event/stream/error")
STREAM_AUTHD_EVENT = intern("//event/stream/authd")
RAWDATA_IN_EVENT = intern("//event/rawdata/in")
RAWDATA_OUT_EVENT = intern("//event/rawdata/out")

def hashPassword(sid, password):
    """Create a SHA1-digest string of a session identifier and password """
    import sha
    return sha.new("%s%s" % (sid, password)).hexdigest()

class Authenticator:
    """ Base class for business logic of authenticating an XmlStream

    Subclass this object to enable an XmlStream to authenticate to different
    types of stream hosts (such as clients, components, etc.).

    Rules:
      1. The Authenticator MUST dispatch a L{STREAM_AUTHD_EVENT} when the stream
         has been completely authenticated.
      2. The Authenticator SHOULD reset all state information when
         L{associateWithStream} is called.
      3. The Authenticator SHOULD override L{streamStarted}, and start
         authentication there.


    @type namespace: C{str}
    @cvar namespace: Default namespace for the XmlStream

    @type version: C{int}
    @cvar version: Version attribute for XmlStream. 0.0 will cause the
                   XmlStream to not include a C{version} attribute in the
                   header.

    @type streamHost: C{str}
    @ivar streamHost: Target host for this stream (used as the 'to' attribute)

    @type xmlstream: C{XmlStream}
    @ivar xmlstream: The XmlStream that needs authentication
    """

    namespace = 'invalid' # Default namespace for stream
    version = 0.0         # Stream version

    def __init__(self, streamHost):
        self.streamHost = streamHost
        self.xmlstream = None

    def connectionMade(self):
        """
        Called by the XmlStream when the underlying socket connection is
        in place. This allows the Authenticator to send an initial root
        element, if it's connecting, or wait for an inbound root from
        the peer if it's accepting the connection

        Subclasses can use self.xmlstream.send() with the provided xmlstream
        parameter to send any initial data to the peer
        """

    def streamStarted(self, rootelem):
        """
        Called by the XmlStream when it has received a root element from
        the connected peer. 
        
        @type rootelem: C{Element}
        @param rootelem: The root element of the XmlStream received from
                         the streamHost
        """

    def associateWithStream(self, xmlstream):
        """
        Called by the XmlStreamFactory when a connection has been made
        to the requested peer, and an XmlStream object has been
        instantiated.

        The default implementation just saves a handle to the new
        XmlStream.

        @type xmlstream: C{XmlStream}
        @param xmlstream: The XmlStream that will be passing events to this
                          Authenticator.
        
        """
        self.xmlstream = xmlstream

class ConnectAuthenticator(Authenticator):
    def connectionMade(self):
        # Generate stream header
        if self.version == 1.0:
            sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' version='1.0'>" % \
                 (self.namespace)
        else:
            sh = "<stream:stream xmlns='%s' xmlns:stream='http://etherx.jabber.org/streams' to='%s'>" % \
                 (self.namespace, self.streamHost)
        self.xmlstream.send(sh)
    
class XmlStream(protocol.Protocol, utility.EventDispatcher):
    def __init__(self, authenticator):
        utility.EventDispatcher.__init__(self)
        self.stream = None
        self.authenticator = authenticator
        self.sid = None
        self.rawDataOutFn = None
        self.rawDataInFn = None

        # Reset the authenticator
        authenticator.associateWithStream(self)

        # Setup watcher for stream errors
        self.addObserver("/error[@xmlns='http://etherx.jabber.org/streams']", self.streamError)

    def streamError(self, errelem):
        self.dispatch(errelem, STREAM_ERROR_EVENT)
        self.transport.loseConnection()

    ### --------------------------------------------------------------
    ###
    ### Protocol events
    ###
    ### --------------------------------------------------------------
    def connectionMade(self):
        # Setup the parser
        self.stream = domish.elementStream()
        self.stream.DocumentStartEvent = self.onDocumentStart
        self.stream.ElementEvent = self.onElement
        self.stream.DocumentEndEvent = self.onDocumentEnd

        self.dispatch(self, STREAM_CONNECTED_EVENT)

        self.authenticator.connectionMade()

    def dataReceived(self, buf):
        try:
            if self.rawDataInFn: self.rawDataInFn(buf)
            self.stream.parse(buf)
        except domish.ParserError:
            self.dispatch(self, STREAM_ERROR_EVENT)
            self.transport.loseConnection()

    def connectionLost(self, _):
        self.dispatch(self, STREAM_END_EVENT)
        self.stream = None
        
    ### --------------------------------------------------------------
    ###
    ### DOM events
    ###
    ### --------------------------------------------------------------
    def onDocumentStart(self, rootelem):
        if rootelem.hasAttribute("id"):
            self.sid = rootelem["id"]                  # Extract stream identifier
        self.authenticator.streamStarted(rootelem) # Notify authenticator
        self.dispatch(self, STREAM_START_EVENT)    

    def onElement(self, element):
        self.dispatch(element)

    def onDocumentEnd(self):
        self.transport.loseConnection()

    def setDispatchFn(self, fn):
        self.stream.ElementEvent = fn

    def resetDispatchFn(self):
        self.stream.ElementEvent = self.onElement

    def send(self, obj):
        if isinstance(obj, domish.Element):
            obj = obj.toXml()
            
        if self.rawDataOutFn:
            self.rawDataOutFn(obj)
            
        self.transport.write(obj)


class XmlStreamFactory(protocol.ReconnectingClientFactory):
    def __init__(self, authenticator):
        self.authenticator = authenticator
        self.bootstraps = []

    def buildProtocol(self, _):
        self.resetDelay()
        # Create the stream and register all the bootstrap observers
        xs = XmlStream(self.authenticator)
        xs.factory = self
        for event, fn in self.bootstraps: xs.addObserver(event, fn)
        return xs

    def addBootstrap(self, event, fn):
        self.bootstraps.append((event, fn))

    def removeBootstrap(self, event, fn):
        self.bootstraps.remove((event, fn))




        
