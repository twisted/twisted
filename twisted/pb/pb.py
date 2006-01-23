# -*- test-case-name: twisted.pb.test.test_pb -*-

# This is the primary entry point for newpb

from twisted.python import failure, log, urlpath
from twisted.python.components import registerAdapter
from twisted.internet import defer, protocol
from twisted.application import service, strports

import urlparse
urlparse.uses_netloc.append("pb")

from twisted.pb import ipb, broker, base32, negotiate, tokens, referenceable
from twisted.pb.tokens import PBError
try:
    from twisted.pb import crypto
except ImportError:
    crypto = None
if crypto and not crypto.available:
    crypto = None
try:
    # we want to use the random-number generation code from PyCrypto
    from Crypto.Util import randpool
except ImportError:
    randpool = None
    # fall back to the stdlib 'random' module if we can't get something that
    # uses /dev/random. This form is seeded from the current system time,
    # which is much less satisfying.
    log.msg("Warning: PyCrypto not available, so secure URLs will be "
            "less random than we'd really prefer")
    import random

# names we import so that others can reach them as pb.foo
from twisted.pb.remoteinterface import RemoteInterface
from twisted.pb.referenceable import Referenceable, SturdyRef
from twisted.pb.copyable import Copyable, RemoteCopy, registerRemoteCopy
from twisted.pb.ipb import DeadReferenceError
from twisted.pb.tokens import BananaError


Listeners = []
class Listener(protocol.ServerFactory):
    """I am responsible for a single listening port, which may connect to
    multiple Tubs. I have a strports-based Service, which I will attach as a
    child of one of my Tubs. If that Tub disconnects, I will reparent the
    Service to a remaining one.

    Unencrypted Tubs use a TubID of 'None'. There may be at most one such Tub
    attached to any given Listener."""

    # this also serves as the ServerFactory

    def __init__(self, port, options={}):
        """
        @type port: string
        @param port: a L{twisted.application.strports} -style description.
        """
        name, args, kw = strports.parse(port, None)
        assert name in ("TCP", "UNIX") # TODO: IPv6
        self.port = port
        self.options = options
        self.parentTub = None
        self.tubs = {}
        self.redirects = {}
        self.s = strports.service(port, self)
        Listeners.append(self)

    def getPortnum(self):
        """When this Listener was created with a strport string of '0' or
        'tcp:0' (meaning 'please allocate me something'), and if the Listener
        is active (it is attached to a Tub which is in the 'running' state),
        this method will return the port number that was allocated. This is
        useful for the following pattern:

         t = PBService()
         l = t.listenOn('tcp:0')
         t.setLocation('localhost:%d' % l.getPortnum())
        """

        assert self.s.running
        name, args, kw = strports.parse(self.port, None)
        assert name in ("TCP",)
        return self.s._port.getHost().port

    def __repr__(self):
        if self.tubs:
            return "<Listener at 0x%x on %s with tubs %s>" % (
                abs(id(self)),
                self.port,
                ",".join([str(k) for k in self.tubs.keys()]))
        return "<Listener at 0x%x on %s with no tubs>" % (abs(id(self)),
                                                          self.port)

    def addTub(self, tub):
        if tub.tubID in self.tubs:
            if tub.tubID is None:
                raise RuntimeError("This Listener (on %s) already has an "
                                   "unencrypted Tub, you cannot add a second "
                                   "one" % self.port)
            raise RuntimeError("This Listener (on %s) is already connected "
                               "to TubID '%s'" % (self,port, tub.tubID))
        self.tubs[tub.tubID] = tub
        if self.parentTub is None:
            self.parentTub = tub
            self.s.setServiceParent(self.parentTub)
    def removeTub(self, tub):
        # this returns a Deferred, since the removal might cause the Listener
        # to shut down
        del self.tubs[tub.tubID]
        if self.parentTub is tub:
            # we need to switch to a new one
            tubs = self.tubs.values()
            if tubs:
                self.parentTub = tubs[0]
                # TODO: I want to do this without first doing
                # disownServiceParent, so the port remains listening. Can we
                # do this? It looks like setServiceParent does
                # disownServiceParent first, so it may glitch.
                self.s.setServiceParent(self.parentTub)
            else:
                # no more tubs, this Listener will go away now
                d = self.s.disownServiceParent()
                Listeners.remove(self)
                return d
        return defer.succeed(None)

    def getService(self):
        return self.s

    def addRedirect(self, tubID, location):
        assert tubID is not None # unencrypted Tubs don't get redirects
        self.redirects[tubID] = location
    def removeRedirect(self, tubID):
        del self.redirects[tubID]

    def buildProtocol(self, addr):
        """Return a Broker attached to me (as the service provider).
        """
        proto = negotiate.Negotiation()
        proto.initServer(self)
        proto.factory = self
        return proto

    def lookupTubID(self, tubID):
        return self.tubs.get(tubID), self.redirects.get(tubID)


class PBService(service.MultiService):
    """I am a presence in the PB universe, also known as a Tub.

    This is the primary entry point for all PB-using applications, both
    clients and servers.

    I am known to the outside world by a base URL, which may include
    authentication information (a yURL). This is my 'TubID'.

    I contain Referenceables, and manage RemoteReferences to Referenceables
    that live in other Tubs.

    @param encrypted: True if this Tub should provide secure references.
                      'True' is the default if crypto is available.
    @param certData: if provided, use it as a certificate rather than
                     generating a new one. This is a PEM-encoded
                     private/public keypair, as returned by Tub.getCertData()
    @param options: a dictionary of options that can influence connection
                    connection negotiation. Currently defined keys are:
                     - debug_slow: if True, wait half a second between
                                   each negotiation response

    @itype tubID: string
    @ivar  tubID: a global identifier for this Tub, possibly including
                  authentication information, hash of SSL certificate

    @ivar brokers: maps TubIDs to L{Broker} instances

    @itype listeners: maps strport to TCPServer service

    @ivar referenceToName: maps Referenceable to a name
    @ivar nameToReference: maps name to Referenceable

    """

    unsafeTracebacks = True # TODO: better way to enable this
    debugBanana = False
    NAMEBITS = 160 # length of swissnumber for each reference
    TUBIDBITS = 16 # length of non-crypto tubID
    if randpool:
        randpool = randpool.RandomPool()
    else:
        randpool = None

    def __init__(self, encrypted=None, certData=None, options={}):
        service.MultiService.__init__(self)
        if encrypted is None:
            if crypto:
                encrypted = True
            else:
                encrypted = False
        assert encrypted in (True, False)
        self.options = options
        self.listeners = []
        self.locationHints = []
        self.encrypted = encrypted
        if encrypted and not crypto:
            raise RuntimeError("crypto for PB is not available, "
                               "try importing twisted.pb.crypto and see "
                               "what happens")
        if encrypted:
            if certData:
                cert = crypto.sslverify.PrivateCertificate.loadPEM(certData)
            else:
                cert = self.createCertificate()
            self.myCertificate = cert
            self.tubID = crypto.digest32(cert.digest("sha1"))
        else:
            self.myCertificate = None
            self.tubID = None

        # local Referenceables
        self.nameToReference = {}
        self.referenceToName = {}
        # remote stuff. Most of these use a TubRef (or NoAuthTubRef) as a
        # dictionary key
        self.tubConnectors = {} # maps TubRef to a TubConnector
        self.waitingForBrokers = {} # maps TubRef to list of Deferreds
        self.brokers = {} # maps TubRef to a Broker that connects to them
        self.unencryptedBrokers = [] # inbound Brokers without TubRefs

    def createCertificate(self):
        # this is copied from test_sslverify.py
        dn = crypto.DistinguishedName(commonName="newpb_thingy")
        keypair = crypto.KeyPair.generate()
        req = keypair.certificateRequest(dn)
        certData = keypair.signCertificateRequest(dn, req,
                                                  lambda dn: True,
                                                  132)
        cert = keypair.newCertificate(certData)
        #opts = cert.options()
        # 'opts' can be given to reactor.listenSSL, or to transport.startTLS

        return cert

    def getCertData(self):
        # the string returned by this method can be used as the certData=
        # argument to create a new PBService with the same identity. TODO:
        # actually test this, I don't know if dump/keypair.newCertificate is
        # the right pair of methods.
        return self.myCertificate.dumpPEM()

    def setLocation(self, *hints):
        """Tell this service what its location is: a host:port description of
        how to reach it from the outside world. You need to use this because
        the Tub can't do it without help. If you do a
        C{s.listenOn('tcp:1234')}, and the host is known as
        C{foo.example.com}, then it would be appropriate to do:

         s.setLocation('foo.example.com:1234')

        You must set the location before you can register any references.

        Encrypted Tubs can have multiple location hints, just provide
        multiple arguments. Unencrypted Tubs can only have one location."""

        if not self.encrypted and len(hints) > 1:
            raise PBError("Unencrypted tubs may only have one location hint")
        self.locationHints = hints

    def listenOn(self, what, options={}):
        """Start listening for connections.

        @type  what: string or Listener instance
        @param what: a L{twisted.application.strports} -style description,
                     or a L{Listener} instance returned by a previous call to
                     listenOn.
        @param options: a dictionary of options that can influence connection
                        negotiation before the target Tub has been determined

        @return: The Listener object that was created. This can be used to
        stop listening later on, to have another Tub listen on the same port,
        and to figure out which port was allocated when you used a strports
        specification of'tcp:0'. """

        if type(what) is str:
            l = Listener(what, options)
        else:
            assert not options
            l = what
        assert l not in self.listeners
        l.addTub(self)
        self.listeners.append(l)
        return l

    def stopListeningOn(self, l):
        self.listeners.remove(l)
        d = l.removeTub(self)
        return d

    def getListeners(self):
        """Return the set of Listener objects that allow the outside world to
        connect to this Tub."""
        return self.listeners[:]

    def clone(self):
        """Return a new Tub, listening on the same ports as this one. """
        t = PBService(encrypted=self.encrypted)
        for l in self.listeners:
            t.listenOn(l)
        return t

    def stopService(self):
        dl = []
        for l in self.listeners:
            # TODO: rethink this, what I want is for stopService to cause all
            # Listeners to shut down, but I'm not sure this is the right way
            # to do it.
            dl.append(l.removeTub(self))
        dl.append(service.MultiService.stopService(self))
        for b in self.brokers.values():
            d = defer.maybeDeferred(b.transport.loseConnection)
            dl.append(d)
        for b in self.unencryptedBrokers:
            d = defer.maybeDeferred(b.transport.loseConnection)
            dl.append(d)
        return defer.DeferredList(dl)

    def generateSwissnumber(self, bits):
        if self.randpool:
            bytes = self.randpool.get_bytes(bits/8)
        else:
            bytes = "".join([chr(random.randint(0,255))
                             for n in range(bits/8)])
        return base32.encode(bytes)

    def buildURL(self, name):
        if self.encrypted:
            # TODO: IPv6 dotted-quad addresses have colons, but need to have
            # host:port
            hints = ",".join(self.locationHints)
            return "pb://" + self.tubID + "@" + hints + "/" + name
        return "pbu://" + self.locationHints[0] + "/" + name

    def registerReference(self, ref, name=None):
        """Make a Referenceable available to the outside world. A URL is
        returned which can be used to access this object. This registration
        will remain in effect until explicitly unregistered.

        @type  name: string (optional)
        @param name: if provided, the object will be registered with this
                     name. If not, a random (unguessable) string will be
                     used.
        @rtype: string
        @return: the URL which points to this object. This URL can be passed
        to PBService.getReference() in any PBService on any host which can
        reach this one.
        """

        if not self.locationHints:
            raise RuntimeError("you must setLocation() before "
                               "you can registerReference()")
        if self.referenceToName.has_key(ref):
            return self.buildURL(self.referenceToName[ref])
        if name is None:
            name = self.generateSwissnumber(self.NAMEBITS)
        self.referenceToName[ref] = name
        self.nameToReference[name] = ref
        return self.buildURL(name)

    def getReferenceForName(self, name):
        return self.nameToReference[name]

    def getReferenceForURL(self, url):
        # TODO: who should this be used by?
        sturdy = SturdyRef(url)
        assert sturdy.tubID == self.tubID
        return self.getReferenceForName(sturdy.name)

    def getURLForReference(self, ref):
        """Return the global URL for the reference, if there is one, or None
        if there is not."""
        name = self.referenceToName.get(ref)
        if name:
            return self.buildURL(name)
        return None

    def revokeReference(self, ref):
        # TODO
        pass

    def unregisterURL(self, url):
        sturdy = SturdyRef(url)
        name = sturdy.name
        ref = self.nameToReference[name]
        del self.nameToReference[name]
        del self.referenceToName[ref]
        self.revokeReference(ref)

    def unregisterReference(self, ref):
        name = self.referenceToName[ref]
        url = self.buildURL(name)
        sturdy = SturdyRef(url)
        name = sturdy.name
        del self.nameToReference[name]
        del self.referenceToName[ref]
        self.revokeReference(ref)

    def getReference(self, sturdyOrURL):
        """Acquire a RemoteReference for the given SturdyRef/URL.

        @return: a Deferred that fires with the RemoteReference
        """
        if isinstance(sturdyOrURL, SturdyRef):
            sturdy = sturdyOrURL
        else:
            sturdy = SturdyRef(sturdyOrURL)
        # pb->pb: ok, requires crypto
        # pbu->pb: ok, requires crypto
        # pbu->pbu: ok
        # pb->pbu: ok, requires crypto
        if sturdy.encrypted and not crypto:
            e = BananaError("crypto for PB is not available, "
                            "we cannot handle encrypted PB-URLs like %s"
                            % sturdy.getURL())
            return defer.fail(e)
        name = sturdy.name
        d = self.getBrokerForTubRef(sturdy.getTubRef())
        d.addCallback(lambda b: b.getYourReferenceByName(name))
        return d

    def getBrokerForTubRef(self, tubref):
        if tubref in self.brokers:
            return defer.succeed(self.brokers[tubref])

        d = defer.Deferred()
        if tubref not in self.waitingForBrokers:
            self.waitingForBrokers[tubref] = []
        self.waitingForBrokers[tubref].append(d)

        if tubref not in self.tubConnectors:
            # the TubConnector will call our brokerAttached when it finishes
            # negotiation, which will fire waitingForBrokers[tubref].
            c = negotiate.TubConnector(self, tubref)
            self.tubConnectors[tubref] = c
            c.connect()

        return d

    def connectionFailed(self, tubref, why):
        # we previously initiated an outbound TubConnector to this tubref, but
        # it was unable to establish a connection. 'why' is the most useful
        # Failure that occurred (i.e. it is a NegotiationError if we made it
        # that far, otherwise it's a ConnectionFailed).

        if tubref in self.tubConnectors:
            del self.tubConnectors[tubref]
        if tubref in self.brokers:
            # oh, but fortunately an inbound connection must have succeeded.
            # Nevermind.
            return

        # inform hopeful Broker-waiters that they aren't getting one
        if tubref in self.waitingForBrokers:
            waiting = self.waitingForBrokers[tubref]
            del self.waitingForBrokers[tubref]
            for d in waiting:
                d.errback(why)

    def brokerAttached(self, tubref, broker, isClient):
        if not tubref:
            # this is an inbound connection from an unencrypted Tub
            assert not isClient
            # we just track it so we can disconnect it later
            self.unencryptedBrokers.append(broker)
            return

        if tubref in self.tubConnectors:
            # we initiated an outbound connection to this tubref
            if not isClient:
                # however, the connection we got was from an inbound
                # connection. The completed (inbound) connection wins, so
                # abandon the outbound TubConnector
                self.tubConnectors[tubref].shutdown()

            # we don't need the TubConnector any more
            del self.tubConnectors[tubref]

        if tubref in self.brokers:
            # oops, this shouldn't happen but it isn't fatal. Raise
            # BananaError so the Negotiation will drop the connection
            raise BananaError("unexpected duplicate connection")
        self.brokers[tubref] = broker

        # now inform everyone who's been waiting on it
        if tubref in self.waitingForBrokers:
            waiting = self.waitingForBrokers[tubref]
            del self.waitingForBrokers[tubref]
            for d in waiting:
                d.callback(broker)

    def brokerDetached(self, broker, why):
        # the Broker will have already severed all active references
        for tubref in self.brokers.keys():
            if self.brokers[tubref] is broker:
                del self.brokers[tubref]
        if broker in self.unencryptedBrokers:
            self.unencryptedBrokers.remove(broker)

def getRemoteURL_TCP(host, port, pathname, *interfaces):
    url = "pb://%s:%d/%s" % (host, port, pathname)
    s = PBService()
    d = s.getReference(url, interfaces)
    return d
