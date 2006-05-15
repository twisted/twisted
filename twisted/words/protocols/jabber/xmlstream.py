# -*- test-case-name: twisted.words.test.test_jabberxmlstream -*-
#
# Copyright (c) 2001-2006 Twisted Matrix Laboratories.
# See LICENSE for details.

""" XMPP XML Streams

Building blocks for setting up XML Streams, including helping classes for
doing authentication on either client or server side, and working with XML
Stanzas.
"""

from OpenSSL import SSL

from zope.interface import Interface, Attribute, directlyProvides

from twisted.internet import defer, ssl
from twisted.python import failure
from twisted.words.protocols.jabber import error
from twisted.words.xish import domish, xmlstream
from twisted.words.xish.xmlstream import STREAM_CONNECTED_EVENT
from twisted.words.xish.xmlstream import STREAM_START_EVENT
from twisted.words.xish.xmlstream import STREAM_END_EVENT
from twisted.words.xish.xmlstream import STREAM_ERROR_EVENT

STREAM_AUTHD_EVENT = intern("//event/stream/authd")
TLS_FAILED_EVENT = intern("//event/tls/failed")

NS_STREAMS = 'http://etherx.jabber.org/streams'
NS_XMPP_TLS = 'urn:ietf:params:xml:ns:xmpp-tls'

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
    """ XMPP XML Stream protocol handler.

    The use of TLS is controlled by the C{useTls} attribute. It can have
    three values:

     - 0: never initiate TLS
     - 1: initiate TLS when available
     - 2: always initiate TLS or dispatch L{TLS_FAILED_EVENT} if not
          available

    L{TLS_FAILED_EVENT} is also fired when TLS negotiation failed.

    The C{tlsEstablished} attribute is set to True whenever TLS was negotiated
    succesfully.

    The C{features} attribute is a L{dict} mapping (uri, name) tuples to
    their respective received feature elements.
    """

    version = (1, 0)        # Stream version; pair of integers: (major, minor)
    namespace = 'invalid'   # Default namespace for stream (in ASCII)
    thisHost = None         # Hostname of this entity
    otherHost = None        # Hostname of the entity we connect to
    sid = None              # Session identifier (in ASCII)
    initiating = True       # True if this is the initiating stream
    _headerSent = False     # True if the stream header has been sent
    features = {}           # Stream features dictionary {(uri, name): element}
    useTls = 2              # 0 = never, 1 = whenever possible, 2 = always
    tlsEstablished = False  # True if TLS has been succesfully negotiated
    prefixes = {NS_STREAMS: 'stream'}

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
        """ Called when a stream:error element has been received.

        Dispatches a L{STREAM_ERROR_EVENT} event with the error element to
        allow for cleanup actions and drops the connection.

        @param errelem: The received error element.
        @type errelem: L{domish.Element}
        """
        self.dispatch(errelem, STREAM_ERROR_EVENT)
        self.transport.loseConnection()

    def startTLS(self):
        def proceed(obj):
            print "proceed"
            ctx = ssl.ClientContextFactory()
            ctx.method = SSL.TLSv1_METHOD   # We only do TLS, no SSL
            self.transport.startTLS(ctx)
            self.reset()
            self.tlsEstablished = 1
            self.sendHeader()

        def failure(obj):
            self.factory.stopTrying()
            self.dispatch(obj, TLS_FAILED_EVENT)

        self.addOnetimeObserver("/proceed", proceed)
        self.addOnetimeObserver("/failure", failure)
        self.send("<starttls xmlns='%s'/>" % NS_XMPP_TLS)

    def onFeatures(self, features):
        """ Called when a stream:features element has been received.
    
        Stores the received features in the C{features} attribute, checks the
        need for initiating TLS and notifies the authenticator of the start of
        the stream.

        @param features: The received features element.
        @type features: L{domish.Element}
        """
        self.features = {}
        for feature in features.elements():
            self.features[(feature.uri, feature.name)] = feature
        
        starttls = (NS_XMPP_TLS, 'starttls') in self.features
        
        if self.tlsEstablished or self.useTls == 0 or \
           (self.useTls == 1 and not starttls):
            self.authenticator.streamStarted()
        elif not self.tlsEstablished and self.useTls in (1, 2) and starttls:
            self.startTLS()
        else:
            self.factory.stopTrying()
            self.dispatch(None, TLS_FAILED_EVENT)
            self.transport.loseConnection()
            
    def hasFeature(self, uri, name):
        """ Report if a certain feature is supported.
        
        @param uri: Feature namespace URI.
        @type uri: L{str}
        @param name: Feature name.
        @type name: L{str}
        """
        return (uri, name) in self.features

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

    def send(self, obj):
        """ Send data over the stream.

        This overrides L{xmlstream.Xmlstream.send} to use the default namespace
        of the stream header when serializing L{domish.IElement}s. It is
        assumed that if you pass an object that provides L{domish.IElement},
        it represents a direct child of the stream's root element.
        """

        if domish.IElement.providedBy(obj):
            obj = obj.toXml(prefixes=self.prefixes,
                            defaultUri=self.namespace,
                            prefixesInScope=self.prefixes.values())

        xmlstream.XmlStream.send(self, obj)

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

class IIQResponseTracker(Interface):
    """ IQ response tracker interface.

    The XMPP stanza C{iq} has a request-response nature that fits
    naturally with deferreds. You send out a request and when the response
    comes back a deferred is fired.
    
    The L{IQ} class implements a C{send} method that returns a deferred. This
    deferred is put in a dictionary that is kept in an L{XmlStream} object,
    keyed by the request stanzas C{id} attribute.

    An object providing this interface (usually an instance of L{XmlStream}),
    keeps the said dictionary and sets observers on the iq stanzas of type
    C{result} and C{error} and lets the callback fire the associated deferred.
    """

    iqDeferreds = Attribute("Dictionary of deferreds waiting for an iq "
                             "response")

def upgradeWithIQResponseTracker(xmlstream):
    """ Enhances an XmlStream for iq response tracking.

    This makes an L{XmlStream} object provide L{IIQResponseTracker}. When a
    response is an error iq stanza, the deferred has its errback invoked with a
    failure that holds a L{StanzaException<error.StanzaException>} that is
    easier to examine.
    """

    def callback(iq):
        if getattr(iq, 'handled', False):
            return

        try:
            d = xmlstream.iqDeferreds[iq["id"]]
        except KeyError:
            pass
        else:
            del iq["id"]
            iq.handled = True
            if iq['type'] == 'error':
                d.errback(failure.Failure(error.exceptionFromStanza(iq)))
            else:
                d.callback(iq)

    xmlstream.iqDeferreds = {}
    xmlstream.addObserver('/iq[@type="result"]', callback)
    xmlstream.addObserver('/iq[@type="error"]', callback)
    directlyProvides(xmlstream, IIQResponseTracker)

class IQ(domish.Element):
    """ Wrapper for an iq stanza.
   
    Iq stanzas are used for communications with a request-response behaviour.
    Each iq request is associated with an XML stream and has its own unique id
    to be able to track the response.
    """

    def __init__(self, xmlstream, type = "set"):
        """
        @type xmlstream: L{xmlstream.XmlStream}
        @param xmlstream: XmlStream to use for transmission of this IQ

        @type type: L{str}
        @param type: IQ type identifier ('get' or 'set')
        """

        domish.Element.__init__(self, (None, "iq"))
        self.addUniqueId()
        self["type"] = type
        self._xmlstream = xmlstream

    def send(self, to=None):
        """ Send out this iq.

        Returns a deferred that is fired when an iq response with the same id
        is received. Result responses will be passed to the deferred callback.
        Error responses will be transformed into a
        L{StanzaError<error.StanzaError>} and result in the errback of the
        deferred being invoked. 

        @rtype: L{defer.Deferred}
        """

        if to is not None:
            self["to"] = to

        if not IIQResponseTracker.providedBy(self._xmlstream):
            upgradeWithIQResponseTracker(self._xmlstream)

        d = defer.Deferred()
        self._xmlstream.iqDeferreds[self['id']] = d
        self._xmlstream.send(self)
        return d
