# Copyright 2005 Divmod, Inc.  See LICENSE file for details

from twisted.python import log, filepath
from twisted.protocols import amp
from twisted.test import iosim
from twisted.trial import unittest
from twisted.internet import protocol, defer, error

from twisted.internet.error import PeerVerifyError

class TestProto(protocol.Protocol):
    def __init__(self, onConnLost, dataToSend):
        self.onConnLost = onConnLost
        self.dataToSend = dataToSend

    def connectionMade(self):
        self.data = []
        self.transport.write(self.dataToSend)

    def dataReceived(self, bytes):
        self.data.append(bytes)
        # self.transport.loseConnection()

    def connectionLost(self, reason):
        self.onConnLost.callback(self.data)

class SimpleSymmetricProtocol(amp.AMP):

    def sendHello(self, text):
        return self.callRemoteString(
            "hello",
            hello=text)

    def amp_HELLO(self, box):
        return amp.Box(hello=box['hello'])

    def amp_HOWDOYOUDO(self, box):
        return amp.QuitBox(howdoyoudo='world')

class UnfriendlyGreeting(Exception):
    """Greeting was insufficiently kind.
    """

class DeathThreat(Exception):
    """Greeting was insufficiently kind.
    """

class UnknownProtocol(Exception):
    """Asked to switch to the wrong protocol.
    """


class TransportPeer(amp.Argument):
    # this serves as some informal documentation for how to get variables from
    # the protocol or your environment and pass them to methods as arguments.
    def retrieve(self, d, name, proto):
        return ''

    def fromStringProto(self, notAString, proto):
        return proto.transport.getPeer()

    def toBox(self, name, strings, objects, proto):
        return

class Hello(amp.Command):

    commandName = 'hello'

    arguments = [('hello', amp.String()),
                 ('optional', amp.Boolean(optional=True)),
                 ('print', amp.Unicode(optional=True)),
                 ('from', TransportPeer(optional=True))]

    response = [('hello', amp.String()),
                ('print', amp.Unicode(optional=True))]

    errors = {UnfriendlyGreeting: 'UNFRIENDLY'}

    fatalErrors = {DeathThreat: 'DEAD'}

class NoAnswerHello(Hello):
    commandName = Hello.commandName
    requiresAnswer = False

class FutureHello(amp.Command):
    commandName = 'hello'

    arguments = [('hello', amp.String()),
                 ('optional', amp.Boolean(optional=True)),
                 ('print', amp.Unicode(optional=True)),
                 ('from', TransportPeer(optional=True)),
                 ('bonus', amp.String(optional=True)), # addt'l arguments
                                                       # should generally be
                                                       # added at the end, and
                                                       # be optional...
                 ]

    response = [('hello', amp.String()),
                ('print', amp.Unicode(optional=True))]

    errors = {UnfriendlyGreeting: 'UNFRIENDLY'}

class WTF(amp.Command):
    """
    An example of an invalid command.
    """


class BrokenReturn(amp.Command):
    """ An example of a perfectly good command, but the handler is going to return
    None...
    """

    commandName = 'broken_return'

class Goodbye(amp.Command):
    # commandName left blank on purpose: this tests implicit command names.
    response = [('goodbye', amp.String())]
    responseType = amp.QuitBox

class Howdoyoudo(amp.Command):
    commandName = 'howdoyoudo'
    # responseType = amp.QuitBox

class WaitForever(amp.Command):
    commandName = 'wait_forever'

class GetList(amp.Command):
    commandName = 'getlist'
    arguments = [('length', amp.Integer())]
    response = [('body', amp.AmpList([('x', amp.Integer())]))]

class SecuredPing(amp.Command):
    # XXX TODO: actually make this refuse to send over an insecure connection
    response = [('pinged', amp.Boolean())]

class TestSwitchProto(amp.ProtocolSwitchCommand):
    commandName = 'Switch-Proto'

    arguments = [
        ('name', amp.String()),
        ]
    errors = {UnknownProtocol: 'UNKNOWN'}

class SingleUseFactory(protocol.ClientFactory):
    def __init__(self, proto):
        self.proto = proto
        self.proto.factory = self

    def buildProtocol(self, addr):
        p, self.proto = self.proto, None
        return p

    reasonFailed = None

    def clientConnectionFailed(self, connector, reason):
        self.reasonFailed = reason
        return
    
THING_I_DONT_UNDERSTAND = 'gwebol nargo'
class ThingIDontUnderstandError(Exception):
    pass

class FactoryNotifier(amp.AMP):
    factory = None
    def connectionMade(self):
        if self.factory is not None:
            self.factory.theProto = self
            if hasattr(self.factory, 'onMade'):
                self.factory.onMade.callback(None)

    def emitpong(self):
        from twisted.internet.interfaces import ISSLTransport
        if not ISSLTransport.providedBy(self.transport):
            raise DeathThreat("only send secure pings over secure channels")
        return {'pinged': True}
    SecuredPing.responder(emitpong)


class SimpleSymmetricCommandProtocol(FactoryNotifier):
    maybeLater = None
    def __init__(self, onConnLost=None):
        amp.AMP.__init__(self)
        self.onConnLost = onConnLost

    def sendHello(self, text):
        return self.callRemote(Hello, hello=text)

    def sendUnicodeHello(self, text, translation):
        return self.callRemote(Hello, hello=text, Print=translation)

    greeted = False

    def cmdHello(self, hello, From, optional=None, Print=None):
        assert From == self.transport.getPeer()
        if hello == THING_I_DONT_UNDERSTAND:
            raise ThingIDontUnderstandError()
        if hello.startswith('fuck'):
            raise UnfriendlyGreeting("Don't be a dick.")
        if hello == 'die':
            raise DeathThreat("aieeeeeeeee")
        result = dict(hello=hello)
        if Print is not None:
            result.update(dict(Print=Print))
        self.greeted = True
        return result
    Hello.responder(cmdHello)

    def cmdGetlist(self, length):
        return {'body': [dict(x=1)] * length}
    GetList.responder(cmdGetlist)

    def waitforit(self):
        self.waiting = defer.Deferred()
        return self.waiting
    WaitForever.responder(waitforit)

    def howdo(self):
        return dict(howdoyoudo='world')
    Howdoyoudo.responder(howdo)

    def saybye(self):
        return dict(goodbye="everyone")
    Goodbye.responder(saybye)

    def switchToTestProtocol(self, fail=False):
        if fail:
            name = 'no-proto'
        else:
            name = 'test-proto'
        p = TestProto(self.onConnLost, SWITCH_CLIENT_DATA)
        return self.callRemote(
            TestSwitchProto,
            SingleUseFactory(p), name=name).addCallback(lambda ign: p)

    def switchit(self, name):
        if name == 'test-proto':
            return TestProto(self.onConnLost, SWITCH_SERVER_DATA)
        raise UnknownProtocol(name)
    TestSwitchProto.responder(switchit)

    def donothing(self):
        return None
    BrokenReturn.responder(donothing)


class DeferredSymmetricCommandProtocol(SimpleSymmetricCommandProtocol):
    def switchit(self, name):
        if name == 'test-proto':
            self.maybeLaterProto = TestProto(self.onConnLost, SWITCH_SERVER_DATA)
            self.maybeLater = defer.Deferred()
            return self.maybeLater
        raise UnknownProtocol(name)
    TestSwitchProto.responder(switchit)


def connectedServerAndClient(ServerClass=SimpleSymmetricProtocol,
                             ClientClass=SimpleSymmetricProtocol,
                             *a, **kw):
    """Returns a 3-tuple: (client, server, pump)
    """
    return iosim.connectedServerAndClient(
        ServerClass, ClientClass,
        *a, **kw)

class TotallyDumbProtocol(protocol.Protocol):
    buf = ''
    def dataReceived(self, data):
        self.buf += data

class LiteralAmp(amp.AMP):
    def __init__(self):
        self.boxes = []

    def ampBoxReceived(self, box):
        self.boxes.append(box)
        return

class ParsingTest(unittest.TestCase):

    def test_booleanValues(self):
        """
        Verify that the Boolean parser parses 'True' and 'False', but nothing
        else.
        """
        b = amp.Boolean()
        self.assertEquals(b.fromString("True"), True)
        self.assertEquals(b.fromString("False"), False)
        self.assertRaises(TypeError, b.fromString, "ninja")
        self.assertRaises(TypeError, b.fromString, "true")
        self.assertRaises(TypeError, b.fromString, "TRUE")
        self.assertEquals(b.toString(True), 'True')
        self.assertEquals(b.toString(False), 'False')

    def test_pathValueRoundTrip(self):
        """
        Verify the 'Path' argument can parse and emit a file path.
        """
        fp = filepath.FilePath(self.mktemp())
        p = amp.Path()
        s = p.toString(fp)
        v = p.fromString(s)
        self.assertNotIdentical(fp, v) # sanity check
        self.assertEquals(fp, v)


    def test_sillyEmptyThing(self):
        """
        Test that empty boxes raise an error; they aren't supposed to be sent
        on purpose.
        """
        a = amp.AMP()
        return self.assertRaises(amp.NoEmptyBoxes, a.ampBoxReceived, amp.Box())


    def test_ParsingRoundTrip(self):
        """
        Verify that various kinds of data make it through the encode/parse
        round-trip unharmed.
        """
        c, s, p = connectedServerAndClient(ClientClass=LiteralAmp,
                                           ServerClass=LiteralAmp)

        SIMPLE = ('simple', 'test')
        CE = ('ceq', ': ')
        CR = ('crtest', 'test\r')
        LF = ('lftest', 'hello\n')
        NEWLINE = ('newline', 'test\r\none\r\ntwo')
        NEWLINE2 = ('newline2', 'test\r\none\r\n two')
        BLANKLINE = ('newline3', 'test\r\n\r\nblank\r\n\r\nline')
        BODYTEST = ('body', 'blah\r\n\r\ntesttest')

        testData = [
            [SIMPLE],
            [SIMPLE, BODYTEST],
            [SIMPLE, CE],
            [SIMPLE, CR],
            [SIMPLE, CE, CR, LF],
            [CE, CR, LF],
            [SIMPLE, NEWLINE, CE, NEWLINE2],
            [BODYTEST, SIMPLE, NEWLINE]
            ]

        for test in testData:
            jb = amp.Box()
            jb.update(dict(test))
            jb._sendTo(c)
            p.flush()
            self.assertEquals(s.boxes[-1], jb)

SWITCH_CLIENT_DATA = 'Success!'
SWITCH_SERVER_DATA = 'No, really.  Success.'

class AMPTest(unittest.TestCase):
    def test_helloWorld(self):
        """
        Verify that a simple command can be sent and its response received with
        the simple low-level string-based API.
        """
        c, s, p = connectedServerAndClient()
        L = []
        HELLO = 'world'
        c.sendHello(HELLO).addCallback(L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)


    def test_helloWorldUnicode(self):
        """
        Verify that unicode arguments can be encoded and decoded.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        L = []
        HELLO = 'world'
        HELLO_UNICODE = 'wor\u1234ld'
        c.sendUnicodeHello(HELLO, HELLO_UNICODE).addCallback(L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)
        self.assertEquals(L[0]['Print'], HELLO_UNICODE)


    def test_unknownCommandLow(self):
        """
        Verify that unknown commands using low-level APIs will be rejected with an
        error, but will NOT terminate the connection.
        """
        c, s, p = connectedServerAndClient()
        L = []
        def clearAndAdd(e):
            """
            You can't propagate the error...
            """
            e.trap(amp.UnhandledCommand)
            return "OK"
        c.callRemoteString("WTF").addErrback(clearAndAdd).addCallback(L.append)
        p.flush()
        self.assertEquals(L.pop(), "OK")
        HELLO = 'world'
        c.sendHello(HELLO).addCallback(L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)


    def test_unknownCommandHigh(self):
        """
        Verify that unknown commands using high-level APIs will be rejected with an
        error, but will NOT terminate the connection.
        """
        c, s, p = connectedServerAndClient()
        L = []
        def clearAndAdd(e):
            """
            You can't propagate the error...
            """
            e.trap(amp.UnhandledCommand)
            return "OK"
        c.callRemote(WTF).addErrback(clearAndAdd).addCallback(L.append)
        p.flush()
        self.assertEquals(L.pop(), "OK")
        HELLO = 'world'
        c.sendHello(HELLO).addCallback(L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)


    def test_brokenReturnValue(self):
        """
        It can be very confusing if you write some code which responds to a
        command, but gets the return value wrong.  Most commonly you end up
        returning None instead of a dictionary.

        Verify that if that happens, the framework logs a useful error.
        """
        L = []
        SimpleSymmetricCommandProtocol().dispatchCommand(
            amp.AmpBox(_command=BrokenReturn.commandName)).addErrback(L.append)
        blr = L[0].trap(amp.BadLocalReturn)
        self.failUnlessIn('None', repr(L[0].value))



    def test_unknownArgument(self):
        """
        Verify that unknown arguments are ignored, and not passed to a Python
        function which can't accept them.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        L = []
        HELLO = 'world'
        # c.sendHello(HELLO).addCallback(L.append)
        c.callRemote(FutureHello,
                     hello=HELLO,
                     bonus="I'm not in the book!").addCallback(
            L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)


    def test_simpleReprs(self):
        """
        Verify that the various Box objects repr properly, for debugging.
        """
        self.assertEquals(type(repr(amp._TLSBox())), str)
        self.assertEquals(type(repr(amp._SwitchBox('a'))), str)
        self.assertEquals(type(repr(amp.QuitBox())), str)
        self.assertEquals(type(repr(amp.AmpBox())), str)
        self.failUnless("AmpBox" in repr(amp.AmpBox()))

    def test_keyTooLong(self):
        """
        Verify that a key that is too long will immediately raise a synchronous
        exception.
        """
        c, s, p = connectedServerAndClient()
        L = []
        x = "H" * (0xff+1)
        tl = self.assertRaises(amp.TooLong,
                               c.callRemoteString, "Hello",
                               **{x: "hi"})
        self.failUnless(tl.isKey)
        self.failUnless(tl.isLocal)
        self.failUnlessIdentical(tl.keyName, None)
        self.failUnlessIdentical(tl.value, x)
        self.failUnless(str(len(x)) in repr(tl))
        self.failUnless("key" in repr(tl))


    def test_valueTooLong(self):
        """
        Verify that attempting to send value longer than 64k will immediately
        raise an exception.
        """
        c, s, p = connectedServerAndClient()
        L = []
        x = "H" * (0xffff+1)
        tl = self.assertRaises(amp.TooLong, c.sendHello, x)
        p.flush()
        self.failIf(tl.isKey)
        self.failUnless(tl.isLocal)
        self.failUnlessIdentical(tl.keyName, 'hello')
        self.failUnlessIdentical(tl.value, x)
        self.failUnless(str(len(x)) in repr(tl))
        self.failUnless("value" in repr(tl))
        self.failUnless('hello' in repr(tl))


    def test_helloWorldCommand(self):
        """
        Verify that a simple command can be sent and its response received with
        the high-level value parsing API.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        L = []
        HELLO = 'world'
        c.sendHello(HELLO).addCallback(L.append)
        p.flush()
        self.assertEquals(L[0]['hello'], HELLO)


    def test_helloErrorHandling(self):
        """
        Verify that if a known error type is raised and handled, it will be
        properly relayed to the other end of the connection and translated into
        an exception, and no error will be logged.
        """
        L=[]
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        HELLO = 'fuck you'
        c.sendHello(HELLO).addErrback(L.append)
        p.flush()
        L[0].trap(UnfriendlyGreeting)
        self.assertEquals(str(L[0].value), "Don't be a dick.")


    def test_helloFatalErrorHandling(self):
        """
        Verify that if a known, fatal error type is raised and handled, it will
        be properly relayed to the other end of the connection and translated
        into an exception, no error will be logged, and the connection will be
        terminated.
        """
        L=[]
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        HELLO = 'die'
        c.sendHello(HELLO).addErrback(L.append)
        p.flush()
        L.pop().trap(DeathThreat)
        c.sendHello(HELLO).addErrback(L.append)
        p.flush()
        L.pop().trap(error.ConnectionDone)



    def test_helloNoErrorHandling(self):
        """
        Verify that if an unknown error type is raised, it will be relayed to
        the other end of the connection and translated into an exception, it
        will be logged, and then the connection will be dropped.
        """
        L=[]
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        HELLO = THING_I_DONT_UNDERSTAND
        c.sendHello(HELLO).addErrback(L.append)
        p.flush()
        ure = L.pop()
        ure.trap(amp.UnknownRemoteError)
        c.sendHello(HELLO).addErrback(L.append)
        cl = L.pop()
        cl.trap(error.ConnectionDone)
        # The exception should have been logged.
        self.failUnless(log.flushErrors(ThingIDontUnderstandError))



    def test_lateAnswer(self):
        """
        Verify that a command that does not get answered until after the
        connection terminates will not cause any errors.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        L = []
        HELLO = 'world'
        c.callRemote(WaitForever).addErrback(L.append)
        p.flush()
        self.assertEquals(L, [])
        s.transport.loseConnection()
        p.flush()
        L.pop().trap(error.ConnectionDone)
        # Just make sure that it doesn't error...
        s.waiting.callback({})
        return s.waiting


    def test_requiresNoAnswer(self):
        """
        Verify that a command that requires no answer is run.
        """
        L=[]
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        HELLO = 'world'
        c.callRemote(NoAnswerHello, hello=HELLO)
        p.flush()
        self.failUnless(s.greeted)


    def test_requiresNoAnswerFail(self):
        """
        Verify that commands sent after a failed no-answer request do not complete.
        """
        L=[]
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        HELLO = 'fuck you'
        c.callRemote(NoAnswerHello, hello=HELLO)
        p.flush()
        # This should be logged locally.
        self.failUnless(log.flushErrors(amp.RemoteAmpError))
        HELLO = 'world'
        c.callRemote(Hello, hello=HELLO).addErrback(L.append)
        p.flush()
        L.pop().trap(error.ConnectionDone)
        self.failIf(s.greeted)


    def test_ampListCommand(self):
        """
        Test encoding of an argument that uses the AmpList encoding.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)
        L = []
        c.callRemote(GetList, length=10).addCallback(L.append)
        p.flush()
        values = L.pop().get('body')
        self.assertEquals(values, [{'x': 1}] * 10)


    def test_failEarlyOnArgSending(self):
        """
        Verify that if we pass an invalid argument list (omitting an argument), an
        exception will be raised.
        """
        okayCommand = Hello(Hello="What?")
        self.assertRaises(amp.InvalidSignature, Hello)


    def test_protocolSwitch(self, switcher=SimpleSymmetricCommandProtocol,
                            spuriousTraffic=False):
        """
        Verify that it is possible to switch to another protocol mid-connection and
        send data to it successfully.
        """
        self.testSucceeded = False

        serverDeferred = defer.Deferred()
        serverProto = switcher(serverDeferred)
        clientDeferred = defer.Deferred()
        clientProto = switcher(clientDeferred)
        c, s, p = connectedServerAndClient(ServerClass=lambda: serverProto,
                                           ClientClass=lambda: clientProto)

        if spuriousTraffic:
            wfdr = []           # remote
            wfd = c.callRemote(WaitForever).addErrback(wfdr.append)
        switchDeferred = c.switchToTestProtocol()
        if spuriousTraffic:
            self.assertRaises(amp.ProtocolSwitched, c.sendHello, 'world')

        def cbConnsLost(((serverSuccess, serverData),
                         (clientSuccess, clientData))):
            self.failUnless(serverSuccess)
            self.failUnless(clientSuccess)
            self.assertEquals(''.join(serverData), SWITCH_CLIENT_DATA)
            self.assertEquals(''.join(clientData), SWITCH_SERVER_DATA)
            self.testSucceeded = True

        def cbSwitch(proto):
            return defer.DeferredList(
                [serverDeferred, clientDeferred]).addCallback(cbConnsLost)

        switchDeferred.addCallback(cbSwitch)
        p.flush()
        if serverProto.maybeLater is not None:
            serverProto.maybeLater.callback(serverProto.maybeLaterProto)
            p.flush()
        if spuriousTraffic:
            # switch is done here; do this here to make sure that if we're
            # going to corrupt the connection, we do it before it's closed.
            s.waiting.callback({})
            p.flush()
        c.transport.loseConnection() # close it
        p.flush()
        self.failUnless(self.testSucceeded)


    def test_protocolSwitchDeferred(self):
        """
        Verify that protocol-switching even works if the value returned from
        the command that does the switch is deferred.
        """
        return self.test_protocolSwitch(switcher=DeferredSymmetricCommandProtocol)

    def test_protocolSwitchFail(self, switcher=SimpleSymmetricCommandProtocol):
        """
        Verify that if we try to switch protocols and it fails, the connection
        stays up and we can go back to speaking AMP.
        """
        self.testSucceeded = False

        serverDeferred = defer.Deferred()
        serverProto = switcher(serverDeferred)
        clientDeferred = defer.Deferred()
        clientProto = switcher(clientDeferred)
        c, s, p = connectedServerAndClient(ServerClass=lambda: serverProto,
                                           ClientClass=lambda: clientProto)
        L = []
        switchDeferred = c.switchToTestProtocol(fail=True).addErrback(L.append)
        p.flush()
        L.pop().trap(UnknownProtocol)
        self.failIf(self.testSucceeded)
        # It's a known error, so let's send a "hello" on the same connection;
        # it should work.
        c.sendHello('world').addCallback(L.append)
        p.flush()
        self.assertEqual(L.pop()['hello'], 'world')


    def test_trafficAfterSwitch(self):
        """
        Verify that attempts to send traffic after a switch will not corrupt
        the nested protocol.
        """
        return self.test_protocolSwitch(spuriousTraffic=True)


    def test_quitBoxQuits(self):
        """
        Verify that commands with a responseType of QuitBox will in fact
        terminate the connection.
        """
        c, s, p = connectedServerAndClient(
            ServerClass=SimpleSymmetricCommandProtocol,
            ClientClass=SimpleSymmetricCommandProtocol)

        L = []
        HELLO = 'world'
        GOODBYE = 'everyone'
        c.sendHello(HELLO).addCallback(L.append)
        p.flush()
        self.assertEquals(L.pop()['hello'], HELLO)
        c.callRemote(Goodbye).addCallback(L.append)
        p.flush()
        self.assertEquals(L.pop()['goodbye'], GOODBYE)
        c.sendHello(HELLO).addErrback(L.append)
        L.pop().trap(error.ConnectionDone)

class PretendRemoteCertificateAuthority:
    def checkIsPretendRemote(self):
        return True

class IOSimCert:
    verifyCount = 0

    def options(self, *ign):
        return self

    def iosimVerify(self, otherCert):
        """
        This isn't a real certificate, and wouldn't work on a real socket, but
        iosim specifies a different API so that we don't have to do any crypto
        math to demonstrate that the right functions get called in the right
        places.
        """
        assert otherCert is self
        self.verifyCount += 1
        return True

class OKCert(IOSimCert):
    def options(self, x):
        assert x.checkIsPretendRemote()
        return self

class GrumpyCert(IOSimCert):
    def iosimVerify(self, otherCert):
        self.verifyCount += 1
        return False

class DroppyCert(IOSimCert):
    def __init__(self, toDrop):
        self.toDrop = toDrop

    def iosimVerify(self, otherCert):
        self.verifyCount += 1
        self.toDrop.loseConnection()
        return True

class SecurableProto(FactoryNotifier):

    serverStarted = 0
    factory = None

    def sfunc(self):
        self.serverStarted += 1

    def verifyFactory(self):
        return [PretendRemoteCertificateAuthority()]

    def getTLSVars(self):
        cert = self.certFactory()
        verify = self.verifyFactory()
        started = self.sfunc
        return dict(
            tls_localCertificate=cert,
            tls_verifyAuthorities=verify,
            tls_started=started)
    amp.StartTLS.responder(getTLSVars)



class TLSTest(unittest.TestCase):
    def test_startingTLS(self):
        """
        Verify that starting TLS and succeeding at handshaking sends all the
        notifications to all the right places.
        """
        cli, svr, p = connectedServerAndClient(
            ServerClass=SecurableProto,
            ClientClass=SecurableProto)

        okc = OKCert()
        svr.certFactory = lambda : okc

        # print c, c.transport
        cli.callRemote(amp.StartTLS,
                       tls_localCertificate=okc,
                       tls_verifyAuthorities=[PretendRemoteCertificateAuthority()])

        # let's buffer something to be delivered securely
        L = []
        d = cli.callRemote(SecuredPing).addCallback(L.append)
        p.flush()
        self.assertEquals(okc.verifyCount, 2) # once for client once for server
        self.assertEquals(svr.serverStarted, 1)
        # this is the server start func, make sure that it hasn't received a
        # duplicate notification.
        self.assertEquals(cli.serverStarted, 0)
        # or for some insane reason been called in the wrong place
        L = []
        d = cli.callRemote(SecuredPing).addCallback(L.append)
        p.flush()
        self.assertEqual(L[0], {'pinged': True})

    def test_startTooManyTimes(self):
        """
        Verify that the protocol will complain if we attempt to renegotiate TLS,
        which we don't support.
        """
        cli, svr, p = connectedServerAndClient(
            ServerClass=SecurableProto,
            ClientClass=SecurableProto)

        okc = OKCert()
        svr.certFactory = lambda : okc

        # print c, c.transport
        cli.callRemote(amp.StartTLS,
                       tls_localCertificate=okc,
                       tls_verifyAuthorities=[PretendRemoteCertificateAuthority()])
        p.flush()
        cli.noPeerCertificate = True # this is totally fake
        self.assertRaises(
            amp.OnlyOneTLS,
            cli.callRemote,
            amp.StartTLS,
            tls_localCertificate=okc,
            tls_verifyAuthorities=[PretendRemoteCertificateAuthority()])

    def test_negotiationFailed(self):
        """
        Verify that starting TLS and failing on both sides at handshaking sends
        notifications to all the right places and terminates the connection.
        """

        badCert = GrumpyCert()

        cli, svr, p = connectedServerAndClient(
            ServerClass=SecurableProto,
            ClientClass=SecurableProto)
        svr.certFactory = lambda : badCert

        cli.callRemote(amp.StartTLS,
                       tls_localCertificate=badCert)

        p.flush()
        self.assertEquals(badCert.verifyCount, 2) # once for client once for server - but both fail
        self.assertEquals(svr.serverStarted, 1)   # this gets called, because
                                                  # it's right after we TRY to
                                                  # initiate SSL...
        # this is the server start func, make sure that it hasn't received a
        # duplicate notification.
        self.assertEquals(cli.serverStarted, 0)
        # or for some insane reason been called in the wrong place
        d = cli.callRemote(SecuredPing)
        p.flush()
        self.assertFailure(d, iosim.OpenSSLVerifyError)

    def test_negotiationFailedByClosing(self):
        """
        Verify that starting TLS and failing by way of a lost connection
        notices that it is probably an SSL problem.
        """

        cli, svr, p = connectedServerAndClient(
            ServerClass=SecurableProto,
            ClientClass=SecurableProto)
        droppyCert = DroppyCert(svr.transport)
        svr.certFactory = lambda : droppyCert

        secure = cli.callRemote(amp.StartTLS,
                                tls_localCertificate=droppyCert)

        p.flush()

        self.assertEquals(droppyCert.verifyCount, 2)
        self.assertEquals(svr.serverStarted, 1)

        self.assertEquals(cli.serverStarted, 0)

        d = cli.callRemote(SecuredPing)
        p.flush()

        # it might be a good idea to move this exception somewhere more
        # reasonable.
        self.assertFailure(d, PeerVerifyError)


class LiveFireBase:
    """
    Utility for connected reactor-using tests.
    """

    def setUp(self):
        from twisted.internet import reactor
        self.serverFactory = protocol.ServerFactory()
        self.serverFactory.protocol = self.serverProto
        self.clientFactory = protocol.ClientFactory()
        self.clientFactory.protocol = self.clientProto
        self.clientFactory.onMade = defer.Deferred()
        self.serverPort = reactor.listenTCP(0, self.serverFactory)
        self.clientConn = reactor.connectTCP(
            '127.0.0.1', self.serverPort.getHost().port,
            self.clientFactory)
        def getProtos(rlst):
            self.cli = self.clientFactory.theProto
            self.svr = self.serverFactory.theProto
        return self.clientFactory.onMade.addCallback(getProtos)

    def tearDown(self):
        L = []
        for conn in self.cli, self.svr:
            if conn.transport is not None:
                # depend on amp's function connection-dropping behavior
                ccl = conn.connectionLost
                d = defer.Deferred().addBoth(ccl)
                conn.connectionLost = d.callback
                conn.transport.loseConnection()
                L.append(d)
        if self.serverPort is not None:
            L.append(self.serverPort.stopListening())
        if self.clientConn is not None:
            self.clientConn.disconnect()
        return defer.DeferredList(L, consumeErrors=True)

def show(x):
    import sys
    sys.stdout.write(x+'\n')
    sys.stdout.flush()

def tempSelfSigned():
    from twisted.internet import ssl

    sharedDN = ssl.DN(CN='shared')
    key = ssl.KeyPair.generate()
    cr = key.certificateRequest(sharedDN)
    sscrd = key.signCertificateRequest(
        sharedDN, cr, lambda dn: True, 1234567)
    cert = key.newCertificate(sscrd)
    return cert

tempcert = tempSelfSigned()

class LiveFireTLSTestCase(LiveFireBase, unittest.TestCase):
    clientProto = SecurableProto
    serverProto = SecurableProto
    def test_liveFireCustomTLS(self):
        """
        Using real, live TLS, actually negotiate a connection.

        This also looks at the 'peerCertificate' attribute's correctness, since
        that's actually loaded using OpenSSL calls, but the main purpose is to
        make sure that we didn't miss anything obvious in iosim about TLS
        negotiations.
        """

        cert = tempcert

        self.svr.verifyFactory = lambda : [cert]
        self.svr.certFactory = lambda : cert
        # only needed on the server, we specify the client below.

        def secured(rslt):
            x = cert.digest()
            def pinged(rslt2):
                # Interesting.  OpenSSL won't even _tell_ us about the peer
                # cert until we negotiate.  we should be able to do this in
                # 'secured' instead, but it looks like we can't.  I think this
                # is a bug somewhere far deeper than here.
                self.failUnlessEqual(x, self.cli.hostCertificate.digest())
                self.failUnlessEqual(x, self.cli.peerCertificate.digest())
                self.failUnlessEqual(x, self.svr.hostCertificate.digest())
                self.failUnlessEqual(x, self.svr.peerCertificate.digest())
            return self.cli.callRemote(SecuredPing).addCallback(pinged)
        return self.cli.callRemote(amp.StartTLS,
                                   tls_localCertificate=cert,
                                   tls_verifyAuthorities=[cert]).addCallback(secured)

class SlightlySmartTLS(SimpleSymmetricCommandProtocol):
    def tlisfy(self):
        return dict(tls_localCertificate=tempcert)

class PlainVanillaLiveFire(LiveFireBase, unittest.TestCase):

    clientProto = SimpleSymmetricCommandProtocol
    serverProto = SimpleSymmetricCommandProtocol

    def test_liveFireDefaultTLS(self):
        """
        Verify that out of the box, we can start TLS to at least encrypt the
        connection, even if we don't have any certificates to use.
        """
        def secured(result):
            return self.cli.callRemote(SecuredPing)
        return self.cli.callRemote(amp.StartTLS).addCallback(secured)

class WithServerTLSVerification(LiveFireBase, unittest.TestCase):
    clientProto = SimpleSymmetricCommandProtocol
    serverProto = SlightlySmartTLS

    def test_anonymousVerifyingClient(self):
        """
        Verify that anonymous clients can verify server certificates.
        """
        def secured(result):
            return self.cli.callRemote(SecuredPing)
        return self.cli.callRemote(amp.StartTLS, tls_verifyAuthorities=[tempcert])
