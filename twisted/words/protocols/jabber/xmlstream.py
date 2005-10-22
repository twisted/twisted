# -*- test-case-name: twisted.words.test.test_jabberxmlstream -*-
#
# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.words.xish import xmlstream
from twisted.words.xish.xmlstream import STREAM_CONNECTED_EVENT
from twisted.words.xish.xmlstream import STREAM_START_EVENT
from twisted.words.xish.xmlstream import STREAM_END_EVENT
from twisted.words.xish.xmlstream import STREAM_ERROR_EVENT

STREAM_AUTHD_EVENT = intern("//event/stream/authd")

NS_STREAMS = 'http://etherx.jabber.org/streams'

def hashPassword(sid, password):
    """Create a SHA1-digest string of a session identifier and password """
    import sha
    return sha.new("%s%s" % (sid, password)).hexdigest()

class Authenticator:
    """ Base class for business logic of authenticating an XmlStream

    Subclass this object to enable an XmlStream to authenticate to different
    types of stream hosts (such as clients, components, etc.).

    Rules:
      1. The Authenticator MUST dispatch a L{STREAM_AUTHD_EVENT} when the
         stream has been completely authenticated.
      2. The Authenticator SHOULD reset all state information when
         L{associateWithStream} is called.
      3. The Authenticator SHOULD override L{streamStarted}, and start
         authentication there.


    @type xmlstream: L{XmlStream}
    @ivar xmlstream: The XmlStream that needs authentication
    """

    def __init__(self):
        self.xmlstream = None

    def connectionMade(self):
        """
        Called by the XmlStream when the underlying socket connection is
        in place. This allows the Authenticator to send an initial root
        element, if it's connecting, or wait for an inbound root from
        the peer if it's accepting the connection

        Subclasses can use self.xmlstream.send() to send any initial data to
        the peer.
        """

    def streamStarted(self):
        """
        Called by the XmlStream when the stream has started.

        A stream is considered to have started when the root element has been
        received and, if applicable, the feature set has been received.
        """

    def associateWithStream(self, xmlstream):
        """
        Called by the XmlStreamFactory when a connection has been made
        to the requested peer, and an XmlStream object has been
        instantiated.

        The default implementation just saves a handle to the new
        XmlStream.

        @type xmlstream: L{XmlStream}
        @param xmlstream: The XmlStream that will be passing events to this
                          Authenticator.
        
        """
        self.xmlstream = xmlstream

class ConnectAuthenticator(Authenticator):
    namespace = None

    def __init__(self, otherHost):
        self.otherHost = otherHost

    def connectionMade(self):
        self.xmlstream.namespace = self.namespace
        self.xmlstream.otherHost = self.otherHost
        self.xmlstream.sendHeader()

class XmlStream(xmlstream.XmlStream):
    """ XMPP XML Stream protocol handler. """
    version = (0, 0)      # Stream version; a pair of integers: (major, minor)
    namespace = 'invalid' # Default namespace for stream (in ASCII)
    thisHost = None       # Hostname of this entity
    otherHost = None      # Hostname of the entity we connect to
    sid = None            # Session identifier (in ASCII)
    initiating = True     # True if this is the initiating stream
    _headerSent = False   # True if the stream header has been sent
    features = None       # Stream features element or None

    def __init__(self, authenticator):
        xmlstream.XmlStream.__init__(self)

        self.authenticator = authenticator

        # Reset the authenticator
        authenticator.associateWithStream(self)

    def reset(self):
        """ Reset XML Stream.

        Resets the XML Parser for incoming data. This is to be used after
        successfully negotiating a new layer, e.g. TLS and SASL. Note that
        registered event observers will continue to be in place.
        """
        self._headerSent = False
        self._initializeStream()

    def streamError(self, errelem):
        """ Called when a stream:error element has bene received.

        Dispatches a L{STREAM_ERROR_EVENT} event with the error element to
        allow for cleanup actions and drops the connection.

        @param errelem: The received error element.
        @type errelem: L{domish.Element}
        """
        self.dispatch(errelem, STREAM_ERROR_EVENT)
        self.transport.loseConnection()

    def onFeatures(self, features):
        """ Called when a stream:features element has been received.
    
        Stores the received features in the C{features} attribute, and
        notifies the authenticator of the start of the stream.

        @param features: The received features element.
        @type features: L{domish.Element}
        """
        self.features = features
        self.authenticator.streamStarted()

    def hasFeature(self, uri, name):
        """ Report if a certain feature is supported.
        
        @param uri: Feature namespace URI.
        @type uri: L{str}
        @param name: Feature name.
        @type name: L{str}
        """
        if self.features is None:
            return False

        for feature in self.features.elements():
            if feature.uri == uri and feature.name == name:
                return True

        return False

    def sendHeader(self):
        """ Send stream header. """
        sh = "<stream:stream xmlns:stream='http://etherx.jabber.org/streams'"
        sh += " xmlns='%s'" % self.namespace

        if self.initiating and self.otherHost:
            sh += " to='%s'" % self.otherHost.encode('utf-8')
        elif not self.initiating:
            if self.thisHost:
                sh += " from='%s'" % self.thisHost.encode('utf-8')
            if self.sid:
                sh += " id='%s'" % self.sid

        if self.version >= (1, 0):
            sh += " version='%d.%d'" % (self.version[0], self.version[1])

        sh += '>'
        self.send(sh)

    def connectionMade(self):
        """ Called when a connection is made.

        Notifies the authenticator when a connection has been made.
        """
        xmlstream.XmlStream.connectionMade(self)
        self.authenticator.connectionMade()

    def onDocumentStart(self, rootelem):
        """ Called when the stream header has been received.

        Extracts the header's C{id} and C{version} attributes from the root
        element. The C{id} attribute is stored in our C{sid} attribute and the
        C{version} attribute is parsed and the minimum of the version we sent
        and the parsed C{version} attribute is stored as a tuple (major, minor)
        in this class' C{version} attribute. If no C{version} attribute was
        present, we assume version 0.0.

        If appropriate (we are the initiating stream and the minimum of our and
        the other party's version is at least 1.0), a one-time observer is
        registered for getting the stream features. The registered function is
        C{onFeatures}.

        Ultimately, the authenticator's C{streamStarted} method will be called.

        @param rootelem: The root element.
        @type rootelem: L{domish.Element}
        """
        xmlstream.XmlStream.onDocumentStart(self, rootelem)

        # Extract stream identifier
        if rootelem.hasAttribute("id"):
            self.sid = rootelem["id"]

        # Extract stream version and take minimum with the version sent 
        if rootelem.hasAttribute("version"):
            version = rootelem["version"].split(".")
            try:
                version = (int(version[0]), int(version[1]))
            except IndexError, ValueError:
                version = (0, 0)
        else:
            version = (0, 0)

        self.version = min(self.version, version)

        # Setup observer for stream errors
        self.addOnetimeObserver("/error[@xmlns='%s']" % NS_STREAMS,
                                self.streamError)
        
        # Setup observer for stream features, if applicable
        if self.initiating and self.version >= (1, 0):
            self.addOnetimeObserver('/features[@xmlns="%s"]' % NS_STREAMS,
                                    self.onFeatures)
        else:
            self.authenticator.streamStarted()

class XmlStreamFactory(xmlstream.XmlStreamFactory):
    def __init__(self, authenticator):
        xmlstream.XmlStreamFactory.__init__(self)
        self.authenticator = authenticator
    
    def buildProtocol(self, _):
        self.resetDelay()
        # Create the stream and register all the bootstrap observers
        xs = XmlStream(self.authenticator)
        xs.factory = self
        for event, fn in self.bootstraps: xs.addObserver(event, fn)
        return xs
