
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Test running processes.
"""
from __future__ import nested_scopes, generators

from twisted.trial import unittest
from twisted.python import log

import gzip
import os
import popen2
import sys
import signal
import warnings
from pprint import pformat

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

# Twisted Imports
from twisted.internet import reactor, protocol, error, interfaces, defer
from twisted.internet.protocol import ProcessProtocol
from twisted.internet.defer import Deferred

from twisted.python import util, runtime
from twisted.python import procutils

class TrivialProcessProtocol(protocol.ProcessProtocol):
    def __init__(self, d):
        self.deferred = d
    
    def processEnded(self, reason):
        self.reason = reason
        self.deferred.callback(None)

class TestProcessProtocol(protocol.ProcessProtocol):

    def connectionMade(self):
        self.stages = [1]
        self.data = ''
        self.err = ''
        self.transport.write("abcd")

    def outReceived(self, data):
        self.data = self.data + data

    def outConnectionLost(self):
        self.stages.append(2)
        if self.data != "abcd":
            raise RuntimeError
        self.transport.write("1234")

    def errReceived(self, data):
        self.err = self.err + data

    def errConnectionLost(self):
        self.stages.append(3)
        if self.err != "1234":
            print 'err != 1234: ' + repr(self.err)
            raise RuntimeError()
        self.transport.write("abcd")
        self.stages.append(4)

    def inConnectionLost(self):
        self.stages.append(5)

    def processEnded(self, reason):
        self.reason = reason
        self.deferred.callback(None)


class EchoProtocol(protocol.ProcessProtocol):

    s = "1234567" * 1001
    n = 10
    finished = 0

    failure = None

    def __init__(self, onEnded):
        self.onEnded = onEnded
        self.count = 0

    def connectionMade(self):
        assert self.n > 2
        for i in range(self.n - 2):
            self.transport.write(self.s)
        # test writeSequence
        self.transport.writeSequence([self.s, self.s])
        self.buffer = self.s * self.n

    def outReceived(self, data):
        if buffer(self.buffer, self.count, len(data)) != buffer(data):
            self.failure = ("wrong bytes received", data, self.count)
            self.transport.closeStdin()
        else:
            self.count += len(data)
            if self.count == len(self.buffer):
                self.transport.closeStdin()

    def processEnded(self, reason):
        self.finished = 1
        if not reason.check(error.ProcessDone):
            self.failure = "process didn't terminate normally: " + str(reason)
        self.onEnded.callback(self)


class SignalProtocol(protocol.ProcessProtocol):
    def __init__(self, deferred, sig):
        self.deferred = deferred
        self.signal = sig

    def outReceived(self, data):
        self.transport.signalProcess(self.signal)

    def processEnded(self, reason):
        if not reason.check(error.ProcessTerminated):
            self.deferred.callback("wrong termination: %s" % reason)
            return
        v = reason.value
        if v.exitCode is not None:
            self.deferred.callback("SIG%s: exitCode is %s, not None" % 
                                   (self.signal, v.exitCode))
            return
        if v.signal != getattr(signal,'SIG'+self.signal):
            self.deferred.callback("SIG%s: .signal was %s, wanted %s" % 
                                   (self.signal, v.signal,
                                    getattr(signal,'SIG'+self.signal)))
            return
        if os.WTERMSIG(v.status) != getattr(signal,'SIG'+self.signal):
            self.deferred.callback('SIG%s: %s'
                                   % (self.signal, os.WTERMSIG(v.status)))
            return
        self.deferred.callback(None)
        

class SignalMixin:
    # XXX: Trial now does this (see
    #      twisted.trial.runner.MethodInfoBase._setUpSigchldHandler)... perhaps
    #      this class should be removed?  Or trial shouldn't bother, and this
    #      class used where it matters?
    #        - spiv, 2005-04-01
    sigchldHandler = None

    def setUpClass(self):
        # make sure SIGCHLD handler is installed, as it should be on
        # reactor.run(). Do this because the reactor may not have been run
        # by the time this test runs.
        if hasattr(reactor, "_handleSigchld") and hasattr(signal, "SIGCHLD"):
            log.msg("Installing SIGCHLD signal handler.")
            self.sigchldHandler = signal.signal(signal.SIGCHLD,
                                                reactor._handleSigchld)
        else:
            log.msg("Skipped installing SIGCHLD signal handler.")

    def tearDownClass(self):
        if self.sigchldHandler:
            log.msg("Uninstalled SIGCHLD signal handler.")
            signal.signal(signal.SIGCHLD, self.sigchldHandler)

class TestManyProcessProtocol(TestProcessProtocol):
    def __init__(self):
        self.deferred = defer.Deferred()

    def processEnded(self, reason):
        self.reason = reason
        if reason.check(error.ProcessDone):
            self.deferred.callback(None)
        else:
            self.deferred.errback(reason)



class UtilityProcessProtocol(ProcessProtocol):
    """
    Helper class for launching a Python process and getting a result from it.

    @ivar program: A string giving a Python program for the child process to
    run.
    """
    program = None

    def run(cls, reactor, argv, env):
        """
        Run a Python process connected to a new instance of this protocol
        class.  Return the protocol instance.

        The Python process is given C{self.program} on the command line to
        execute, in addition to anything specified by C{argv}.  C{env} is
        the complete environment.
        """
        exe = sys.executable
        self = cls()
        reactor.spawnProcess(
            self, exe, [exe, "-c", self.program] + argv, env=env)
        return self
    run = classmethod(run)


    def __init__(self):
        self.bytes = []
        self.requests = []


    def parseChunks(self, bytes):
        """
        Called with all bytes received on stdout when the process exits.
        """
        raise NotImplementedError()


    def getResult(self):
        """
        Return a Deferred which will fire with the result of L{parseChunks}
        when the child process exits.
        """
        d = Deferred()
        self.requests.append(d)
        return d


    def _fireResultDeferreds(self, result):
        """
        Callback all Deferreds returned up until now by L{getResult}
        with the given result object.
        """
        requests = self.requests
        self.requests = None
        for d in requests:
            d.callback(result)


    def outReceived(self, bytes):
        """
        Accumulate output from the child process in a list.
        """
        self.bytes.append(bytes)


    def processEnded(self, reason):
        """
        Handle process termination by parsing all received output and firing
        any waiting Deferreds.
        """
        self._fireResultDeferreds(self.parseChunks(self.bytes))




class GetArgumentVector(UtilityProcessProtocol):
    """
    Protocol which will read a serialized argv from a process and
    expose it to interested parties.
    """
    program = (
        "from sys import stdout, argv\n"
        "stdout.write(chr(0).join(argv))\n"
        "stdout.flush()\n")

    def parseChunks(self, chunks):
        """
        Parse the output from the process to which this protocol was
        connected, which is a single unterminated line of \\0-separated
        strings giving the argv of that process.  Return this as a list of
        str objects.
        """
        return ''.join(chunks).split('\0')



class GetEnvironmentDictionary(UtilityProcessProtocol):
    """
    Protocol which will read a serialized environment dict from a process
    and expose it to interested parties.
    """
    program = (
        "from sys import stdout\n"
        "from os import environ\n"
        "items = environ.iteritems()\n"
        "stdout.write(chr(0).join([k + chr(0) + v for k, v in items]))\n"
        "stdout.flush()\n")

    def parseChunks(self, chunks):
        """
        Parse the output from the process to which this protocol was
        connected, which is a single unterminated line of \\0-separated
        strings giving key value pairs of the environment from that process. 
        Return this as a dictionary.
        """
        environString = ''.join(chunks)
        if not environString:
            return {}
        environ = iter(environString.split('\0'))
        d = {}
        while 1:
            try:
                k = environ.next()
            except StopIteration:
                break
            else:
                v = environ.next()
                d[k] = v
        return d



class ProcessTestCase(SignalMixin, unittest.TestCase):
    """Test running a process."""

    usePTY = False

    def testStdio(self):
        """twisted.internet.stdio test."""
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_twisted.py")
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        env = {"PYTHONPATH": os.pathsep.join(sys.path)}
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=env,
                             path=None, usePTY=self.usePTY)
        p.transport.write("hello, world")
        p.transport.write("abc")
        p.transport.write("123")
        p.transport.closeStdin()

        def processEnded(ign):
            self.assertEquals(p.outF.getvalue(), "hello, worldabc123",
                              "Output follows:\n"
                              "%s\n"
                              "Error message from process_twisted follows:\n"
                              "%s\n" % (p.outF.getvalue(), p.errF.getvalue()))
        return d.addCallback(processEnded)


    def testProcess(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        d = defer.Deferred()
        p = TestProcessProtocol()
        p.deferred = d
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)
        def check(ignored):
            self.assertEquals(p.stages, [1, 2, 3, 4, 5])
            f = p.reason
            f.trap(error.ProcessTerminated)
            self.assertEquals(f.value.exitCode, 23)
            # would .signal be available on non-posix?
            # self.assertEquals(f.value.signal, None)
            try:
                import process_tester, glob
                for f in glob.glob(process_tester.test_file_match):
                    os.remove(f)
            except:
                pass
        d.addCallback(check)
        return d

    def testManyProcesses(self):

        def _check(results, protocols):
            for p in protocols:
                self.assertEquals(p.stages, [1, 2, 3, 4, 5], "[%d] stages = %s" % (id(p.transport), str(p.stages)))
                # test status code
                f = p.reason
                f.trap(error.ProcessTerminated)
                self.assertEquals(f.value.exitCode, 23)

        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tester.py")
        args = [exe, "-u", scriptPath]
        protocols = []
        deferreds = []

        for i in xrange(50):
            p = TestManyProcessProtocol()
            protocols.append(p)
            reactor.spawnProcess(p, exe, args, env=None)
            deferreds.append(p.deferred)

        deferredList = defer.DeferredList(deferreds, consumeErrors=True)
        deferredList.addCallback(_check, protocols)
        return deferredList

    def testEcho(self):
        finished = defer.Deferred()
        p = EchoProtocol(finished)

        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_echoer.py")
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None)

        def asserts(ignored):
            self.failIf(p.failure, p.failure)
            self.failUnless(hasattr(p, 'buffer'))
            self.assertEquals(len(''.join(p.buffer)), len(p.s * p.n))

        def takedownProcess(err):
            p.transport.closeStdin()
            return err

        return finished.addCallback(asserts).addErrback(takedownProcess)
    testEcho.timeout = 60 # XXX This should not be.  There is already a
                          # global timeout value.  Why do you think this
                          # test can complete more quickly?


    def testCommandLine(self):
        args = [r'a\"b ', r'a\b ', r' a\\"b', r' a\\b', r'"foo bar" "', '\tab', '"\\', 'a"b', "a'b"]
        pyExe = sys.executable
        scriptPath = util.sibpath(__file__, "process_cmdline.py")
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, pyExe, [pyExe, "-u", scriptPath]+args, env=None,
                             path=None)

        def processEnded(ign):
            self.assertEquals(p.errF.getvalue(), "")
            recvdArgs = p.outF.getvalue().splitlines()
            self.assertEquals(recvdArgs, args)
        return d.addCallback(processEnded)


    def test_wrongArguments(self):
        """
        Test invalid arguments to spawnProcess: arguments and environment
        must only contains string or unicode, and not null bytes.
        """
        exe = sys.executable
        p = protocol.ProcessProtocol()

        badEnvs = [
            {"foo": 2},
            {"foo": "egg\0a"},
            {3: "bar"},
            {"bar\0foo": "bar"}]

        badArgs = [
            [exe, 2],
            "spam",
            [exe, "foo\0bar"]]

        # Sanity check - this will fail for people who have mucked with
        # their site configuration in a stupid way, but there's nothing we
        # can do about that.
        badUnicode = u'\N{SNOWMAN}'
        try:
            badUnicode.encode(sys.getdefaultencoding())
        except UnicodeEncodeError:
            # Okay, that unicode doesn't encode, put it in as a bad environment
            # key.
            badEnvs.append({badUnicode: 'value for bad unicode key'})
            badEnvs.append({'key for bad unicode value': badUnicode})
            badArgs.append([exe, badUnicode])
        else:
            # It _did_ encode.  Most likely, Gtk2 is being used and the
            # default system encoding is UTF-8, which can encode anything. 
            # In any case, if implicit unicode -> str conversion works for
            # that string, we can't test that TypeError gets raised instead,
            # so just leave it off.
            pass

        for env in badEnvs:
            self.assertRaises(
                TypeError,
                reactor.spawnProcess, p, exe, [exe, "-c", ""], env=env)

        for args in badArgs:
            self.assertRaises(
                TypeError,
                reactor.spawnProcess, p, exe, args, env=None)


    # Use upper-case so that the environment key test uses an upper case
    # name: some versions of Windows only support upper case environment
    # variable names, and I think Python (as of 2.5) doesn't use the right
    # syscall for lowercase or mixed case names to work anyway.
    okayUnicode = u"UNICODE"
    encodedValue = "UNICODE"

    def _deprecatedUnicodeSupportTest(self, processProtocolClass, argv=[], env={}):
        """
        Check that a deprecation warning is emitted when passing unicode to
        spawnProcess for an argv value or an environment key or value. 
        Check that the warning is of the right type, has the right message,
        and refers to the correct file.  Unfortunately, don't check that the
        line number is correct, because that is too hard for me to figure
        out.

        @param processProtocolClass: A L{UtilityProcessProtocol} subclass
        which will be instantiated to communicate with the child process.

        @param argv: The argv argument to spawnProcess.

        @param env: The env argument to spawnProcess.

        @return: A Deferred which fires when the test is complete.
        """
        # Sanity to check to make sure we can actually encode this unicode
        # with the default system encoding.  This may be excessively
        # paranoid. -exarkun
        self.assertEqual(
            self.okayUnicode.encode(sys.getdefaultencoding()),
            self.encodedValue)

        warningsShown = []
        def showwarning(*args):
            warningsShown.append(args)

        origshow = warnings.showwarning
        origregistry = globals().get('__warningregistry__', {})
        try:
            warnings.showwarning = showwarning
            globals()['__warningregistry__'] = {}
            p = processProtocolClass.run(reactor, argv, env)
        finally:
            warnings.showwarning = origshow
            globals()['__warningregistry__'] = origregistry

        d = p.getResult()
        self.assertEqual(len(warningsShown), 1, pformat(warningsShown))
        message, category, filename, lineno = warningsShown[0]
        self.assertEqual(
            message.args,
            ("Argument strings and environment keys/values passed to "
             "reactor.spawnProcess should be str, not unicode.",))
        self.assertIdentical(category, DeprecationWarning)

        # Use starts with because of .pyc/.pyo issues.
        self.failUnless(
            __file__.startswith(filename),
            'Warning in %r, expected %r' % (filename, __file__))

        # It would be nice to be able to check the line number as well, but
        # different configurations actually end up reporting different line
        # numbers (generally the variation is only 1 line, but that's enough
        # to fail the test erroneously...).
        # self.assertEqual(lineno, 202)

        return d

    def test_deprecatedUnicodeArgvSupport(self):
        """
        Test that a unicode string passed for an argument value is allowed
        if it can be encoded with the default system encoding, but that a
        deprecation warning is emitted.
        """
        d = self._deprecatedUnicodeSupportTest(GetArgumentVector, argv=[self.okayUnicode])
        def gotArgVector(argv):
            self.assertEqual(argv, ['-c', self.encodedValue])
        d.addCallback(gotArgVector)
        return d


    def test_deprecatedUnicodeEnvKeySupport(self):
        """
        Test that a unicode string passed for the key of the environment
        dictionary is allowed if it can be encoded with the default system
        encoding, but that a deprecation warning is emitted.
        """
        d = self._deprecatedUnicodeSupportTest(
            GetEnvironmentDictionary, env={self.okayUnicode: self.encodedValue})
        def gotEnvironment(environ):
            self.assertEqual(environ[self.encodedValue], self.encodedValue)
        d.addCallback(gotEnvironment)
        return d


    def test_deprecatedUnicodeEnvValueSupport(self):
        """
        Test that a unicode string passed for the value of the environment
        dictionary is allowed if it can be encoded with the default system
        encoding, but that a deprecation warning is emitted.
        """
        d = self._deprecatedUnicodeSupportTest(
            GetEnvironmentDictionary, env={self.encodedValue: self.okayUnicode})
        def gotEnvironment(environ):
            # On Windows, the environment contains more things than we
            # specified, so only make sure that at least the key we wanted
            # is there, rather than testing the dictionary for exact
            # equality.
            self.assertEqual(environ[self.encodedValue], self.encodedValue)
        d.addCallback(gotEnvironment)
        return d



class TwoProcessProtocol(protocol.ProcessProtocol):
    num = -1
    finished = 0
    def __init__(self):
        self.deferred = defer.Deferred()
    def outReceived(self, data):
        pass
    def processEnded(self, reason):
        self.finished = 1
        self.deferred.callback(None)

class TestTwoProcessesBase:
    def setUp(self):
        self.processes = [None, None]
        self.pp = [None, None]
        self.done = 0
        self.verbose = 0

    def createProcesses(self, usePTY=0):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_reader.py")
        for num in (0,1):
            self.pp[num] = TwoProcessProtocol()
            self.pp[num].num = num
            p = reactor.spawnProcess(self.pp[num],
                                     exe, [exe, "-u", scriptPath], env=None,
                                     usePTY=usePTY)
            self.processes[num] = p

    def close(self, num):
        if self.verbose: print "closing stdin [%d]" % num
        p = self.processes[num]
        pp = self.pp[num]
        self.failIf(pp.finished, "Process finished too early")
        p.loseConnection()
        if self.verbose: print self.pp[0].finished, self.pp[1].finished

    def _onClose(self):
        return defer.gatherResults([ p.deferred for p in self.pp ])

    def testClose(self):
        if self.verbose: print "starting processes"
        self.createProcesses()
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        return self._onClose()

class TestTwoProcessesNonPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    pass

class TestTwoProcessesPosix(TestTwoProcessesBase, SignalMixin, unittest.TestCase):
    def tearDown(self):
        for i in (0,1):
            pp, process = self.pp[i], self.processes[i]
            if not pp.finished:
                try:
                    os.kill(process.pid, signal.SIGTERM)
                except OSError:
                    print "OSError"
        return self._onClose()

    def kill(self, num):
        if self.verbose: print "kill [%d] with SIGTERM" % num
        p = self.processes[num]
        pp = self.pp[num]
        self.failIf(pp.finished, "Process finished too early")
        os.kill(p.pid, signal.SIGTERM)
        if self.verbose: print self.pp[0].finished, self.pp[1].finished

    def testKill(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=0)
        reactor.callLater(1, self.kill, 0)
        reactor.callLater(2, self.kill, 1)
        return self._onClose()

    def testClosePty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.close, 0)
        reactor.callLater(2, self.close, 1)
        return self._onClose()

    def testKillPty(self):
        if self.verbose: print "starting processes"
        self.createProcesses(usePTY=1)
        reactor.callLater(1, self.kill, 0)
        reactor.callLater(2, self.kill, 1)
        return self._onClose()

class FDChecker(protocol.ProcessProtocol):
    state = 0
    data = ""
    failed = None

    def __init__(self, d):
        self.deferred = d

    def fail(self, why):
        self.failed = why
        self.deferred.callback(None)

    def connectionMade(self):
        self.transport.writeToChild(0, "abcd")
        self.state = 1

    def childDataReceived(self, childFD, data):
        #print "[%d] dataReceived(%d,%s)" % (self.state, childFD, data)
        if self.state == 1:
            if childFD != 1:
                self.fail("read '%s' on fd %d (not 1) during state 1" \
                          % (childFD, data))
                return
            self.data += data
            #print "len", len(self.data)
            if len(self.data) == 6:
                if self.data != "righto":
                    self.fail("got '%s' on fd1, expected 'righto'" \
                              % self.data)
                    return
                self.data = ""
                self.state = 2
                #print "state2", self.state
                self.transport.writeToChild(3, "efgh")
                return
        if self.state == 2:
            self.fail("read '%s' on fd %s during state 2" % (childFD, data))
            return
        if self.state == 3:
            if childFD != 1:
                self.fail("read '%s' on fd %s (not 1) during state 3" \
                          % (childFD, data))
                return
            self.data += data
            if len(self.data) == 6:
                if self.data != "closed":
                    self.fail("got '%s' on fd1, expected 'closed'" \
                              % self.data)
                    return
                self.state = 4
            return
        if self.state == 4:
            self.fail("read '%s' on fd %s during state 4" % (childFD, data))
            return

    def childConnectionLost(self, childFD):
        #print "[%d] connectionLost(%d)" % (self.state, childFD)
        if self.state == 1:
            self.fail("got connectionLost(%d) during state 1" % childFD)
            return
        if self.state == 2:
            if childFD != 4:
                self.fail("got connectionLost(%d) (not 4) during state 2" \
                          % childFD)
                return
            self.state = 3
            self.transport.closeChildFD(5)
            return

    def processEnded(self, status):
        #print "[%d] processEnded" % self.state
        rc = status.value.exitCode
        if self.state != 4:
            self.fail("processEnded early, rc %d" % rc)
            return
        if status.value.signal != None:
            self.fail("processEnded with signal %s" % status.value.signal)
            return
        if rc != 0:
            self.fail("processEnded with rc %d" % rc)
            return
        self.deferred.callback(None)

class FDTest(SignalMixin, unittest.TestCase):
    def NOTsetUp(self):
        from twisted.internet import process
        process.Process.debug_child = True
    def NOTtearDown(self):
        from twisted.internet import process
        process.Process.debug_child = False

    def testFD(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_fds.py")
        d = defer.Deferred()
        p = FDChecker(d)
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                             path=None,
                             childFDs={0:"w", 1:"r", 2:2,
                                       3:"w", 4:"r", 5:"w"})
        d.addCallback(lambda x : self.failIf(p.failed, p.failed))
        return d

    def testLinger(self):
        # See what happens when all the pipes close before the process
        # actually stops. This test *requires* SIGCHLD catching to work,
        # as there is no other way to find out the process is done.
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_linger.py")
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                             path=None,
                             childFDs={1:"r", 2:2},
                             )
        def processEnded(ign):
            self.failUnlessEqual(p.outF.getvalue(),
                                 "here is some text\ngoodbye\n")
        return d.addCallback(processEnded)



class Accumulator(protocol.ProcessProtocol):
    """Accumulate data from a process."""

    closed = 0
    endedDeferred = None

    def connectionMade(self):
        # print "connection made"
        self.outF = StringIO.StringIO()
        self.errF = StringIO.StringIO()

    def outReceived(self, d):
        # print "data", repr(d)
        self.outF.write(d)

    def errReceived(self, d):
        # print "err", repr(d)
        self.errF.write(d)

    def outConnectionLost(self):
        # print "out closed"
        pass

    def errConnectionLost(self):
        # print "err closed"
        pass

    def processEnded(self, reason):
        self.closed = 1
        if self.endedDeferred is not None:
            d, self.endedDeferred = self.endedDeferred, None
            d.callback(None)


class PosixProcessBase:
    """Test running processes."""
    usePTY = 0

    def testNormalTermination(self):
        if os.path.exists('/bin/true'): cmd = '/bin/true'
        elif os.path.exists('/usr/bin/true'): cmd = '/usr/bin/true'
        else: raise RuntimeError("true not found in /bin or /usr/bin")

        d = defer.Deferred()
        p = TrivialProcessProtocol(d)
        reactor.spawnProcess(p, cmd, ['true'], env=None,
                             usePTY=self.usePTY)
        def check(ignored):
            p.reason.trap(error.ProcessDone)
            self.assertEquals(p.reason.value.exitCode, 0)
            self.assertEquals(p.reason.value.signal, None)
        d.addCallback(check)
        return d

    def testAbnormalTermination(self):
        if os.path.exists('/bin/false'): cmd = '/bin/false'
        elif os.path.exists('/usr/bin/false'): cmd = '/usr/bin/false'
        else: raise RuntimeError("false not found in /bin or /usr/bin")

        d = defer.Deferred()
        p = TrivialProcessProtocol(d)
        reactor.spawnProcess(p, cmd, ['false'], env=None,
                             usePTY=self.usePTY)

        def check(ignored):
            p.reason.trap(error.ProcessTerminated)
            self.assertEquals(p.reason.value.exitCode, 1)
            self.assertEquals(p.reason.value.signal, None)
        d.addCallback(check)
        return d

    def _testSignal(self, sig):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_signal.py")
        d = defer.Deferred()
        p = SignalProtocol(d, sig)
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath, sig],
                             env=None,
                             usePTY=self.usePTY)
        return d
        
    def testSignalHUP(self):
        d = self._testSignal('HUP')
        d.addCallback(self.failIf)
        return d

    def testSignalINT(self):
        d = self._testSignal('INT')
        d.addCallback(self.failIf)
        return d

    def testSignalKILL(self):
        d = self._testSignal('KILL')
        d.addCallback(self.failIf)
        return d
        

class PosixProcessTestCase(SignalMixin, unittest.TestCase, PosixProcessBase):
    # add three non-pty test cases

    def testStderr(self):
        # we assume there is no file named ZZXXX..., both in . and in /tmp
        if not os.path.exists('/bin/ls'):
            raise RuntimeError("/bin/ls not found")

        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, '/bin/ls',
                             ["/bin/ls",
                              "ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"],
                             env=None, path="/tmp",
                             usePTY=self.usePTY)

        def processEnded(ign):
            self.assertEquals(lsOut, p.errF.getvalue())
        return d.addCallback(processEnded)

    def testProcess(self):
        if os.path.exists('/bin/gzip'): cmd = '/bin/gzip'
        elif os.path.exists('/usr/bin/gzip'): cmd = '/usr/bin/gzip'
        else: raise RuntimeError("gzip not found in /bin or /usr/bin")
        s = "there's no place like home!\n" * 3
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, cmd, [cmd, "-c"], env=None, path="/tmp",
                             usePTY=self.usePTY)
        p.transport.write(s)
        p.transport.closeStdin()

        def processEnded(ign):
            f = p.outF
            f.seek(0, 0)
            gf = gzip.GzipFile(fileobj=f)
            self.assertEquals(gf.read(), s)
        return d.addCallback(processEnded)



class PosixProcessTestCasePTY(SignalMixin, unittest.TestCase, PosixProcessBase):
    """Just like PosixProcessTestCase, but use ptys instead of pipes."""
    usePTY = 1
    # PTYs only offer one input and one output. What still makes sense?
    # testNormalTermination
    # testAbnormalTermination
    # testSignal
    # testProcess, but not without p.transport.closeStdin
    #  might be solveable: TODO: add test if so

    def testOpeningTTY(self):
        exe = sys.executable
        scriptPath = util.sibpath(__file__, "process_tty.py")
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, exe, [exe, "-u", scriptPath], env=None,
                            path=None, usePTY=self.usePTY)
        p.transport.write("hello world!\n")

        def processEnded(ign):
            self.assertEquals(
                p.outF.getvalue(),
                "hello world!\r\nhello world!\r\n",
                "Error message from process_tty follows:\n\n%s\n\n" % p.outF.getvalue())
        return d.addCallback(processEnded)


    def testBadArgs(self):
        pyExe = sys.executable
        pyArgs = [pyExe, "-u", "-c", "print 'hello'"]
        p = Accumulator()
        self.assertRaises(ValueError, reactor.spawnProcess, p, pyExe, pyArgs, usePTY=1, childFDs={1:'r'})

class Win32ProcessTestCase(SignalMixin, unittest.TestCase):
    """Test process programs that are packaged with twisted."""

    def testStdinReader(self):
        pyExe = sys.executable
        scriptPath = util.sibpath(__file__, "process_stdinreader.py")
        p = Accumulator()
        d = p.endedDeferred = defer.Deferred()
        reactor.spawnProcess(p, pyExe, [pyExe, "-u", scriptPath], env=None,
                             path=None)
        p.transport.write("hello, world")
        p.transport.closeStdin()

        def processEnded(ign):
            self.assertEquals(p.errF.getvalue(), "err\nerr\n")
            self.assertEquals(p.outF.getvalue(), "out\nhello, world\nout\n")
        return d.addCallback(processEnded)


    def testBadArgs(self):
        pyExe = sys.executable
        pyArgs = [pyExe, "-u", "-c", "print 'hello'"]
        p = Accumulator()
        self.assertRaises(ValueError, reactor.spawnProcess, p, pyExe, pyArgs, uid=1)
        self.assertRaises(ValueError, reactor.spawnProcess, p, pyExe, pyArgs, gid=1)
        self.assertRaises(ValueError, reactor.spawnProcess, p, pyExe, pyArgs, usePTY=1)
        self.assertRaises(ValueError, reactor.spawnProcess, p, pyExe, pyArgs, childFDs={1:'r'})

class UtilTestCase(unittest.TestCase):
    """
    Tests for process-related helper functions (currently only
    L{procutils.which}.
    """
    def setUp(self):
        """
        Create several directories and files, some of which are executable
        and some of which are not.  Save the current PATH setting.
        """
        j = os.path.join

        base = self.mktemp()

        self.foo = j(base, "foo")
        self.baz = j(base, "baz")
        self.foobar = j(self.foo, "bar")
        self.foobaz = j(self.foo, "baz")
        self.bazfoo = j(self.baz, "foo")
        self.bazbar = j(self.baz, "bar")

        for d in self.foobar, self.foobaz, self.bazfoo, self.bazbar:
            os.makedirs(d)

        for name, mode in [(j(self.foobaz, "executable"), 0700),
                           (j(self.foo, "executable"), 0700),
                           (j(self.bazfoo, "executable"), 0700),
                           (j(self.bazfoo, "executable.bin"), 0700),
                           (j(self.bazbar, "executable"), 0)]:
            f = file(name, "w")
            f.close()
            os.chmod(name, mode)

        self.oldPath = os.environ.get('PATH', None)
        os.environ['PATH'] = os.pathsep.join((
            self.foobar, self.foobaz, self.bazfoo, self.bazbar))


    def tearDown(self):
        """
        Restore the saved PATH setting.
        """
        if self.oldPath is None:
            try:
                del os.environ['PATH']
            except KeyError:
                pass
        else:
            os.environ['PATH'] = self.oldPath


    def test_whichWithoutPATH(self):
        """
        Test that if C{os.environ} does not have a C{'PATH'} key,
        L{procutils.which} returns an empty list.
        """
        del os.environ['PATH']
        self.assertEqual(procutils.which("executable"), [])


    def testWhich(self):
        j = os.path.join
        paths = procutils.which("executable")
        expectedPaths = [j(self.foobaz, "executable"),
                         j(self.bazfoo, "executable")]
        if runtime.platform.isWindows():
            expectedPaths.append(j(self.bazbar, "executable"))
        self.assertEquals(paths, expectedPaths)


    def testWhichPathExt(self):
        j = os.path.join
        old = os.environ.get('PATHEXT', None)
        os.environ['PATHEXT'] = os.pathsep.join(('.bin', '.exe', '.sh'))
        try:
            paths = procutils.which("executable")
        finally:
            if old is None:
                del os.environ['PATHEXT']
            else:
                os.environ['PATHEXT'] = old
        expectedPaths = [j(self.foobaz, "executable"),
                         j(self.bazfoo, "executable"),
                         j(self.bazfoo, "executable.bin")]
        if runtime.platform.isWindows():
            expectedPaths.append(j(self.bazbar, "executable"))
        self.assertEquals(paths, expectedPaths)



class ClosingPipesProcessProtocol(protocol.ProcessProtocol):
    output = ''
    errput = ''

    def __init__(self, outOrErr):
        self.deferred = defer.Deferred()
        self.outOrErr = outOrErr

    def processEnded(self, reason):
        self.deferred.callback(reason)

    def outReceived(self, data):
        self.output += data

    def errReceived(self, data):
        self.errput += data


class ClosingPipes(unittest.TestCase):

    def doit(self, fd):
        p = ClosingPipesProcessProtocol(True)
        p.deferred.addCallbacks(
            callback=lambda _: self.fail("I wanted an errback."),
            errback=self._endProcess, errbackArgs=(p,))
        reactor.spawnProcess(p, sys.executable,
                             [sys.executable, '-u', '-c',
                              r'raw_input(); import sys, os; os.write(%d, "foo\n"); sys.exit(42)' % fd],
                             env=None)
        p.transport.write('go\n')

        if fd == 1:
            p.transport.closeStdout()
        elif fd == 2:
            p.transport.closeStderr()
        else:
            raise RuntimeError

        # make the buggy case not hang
        p.transport.closeStdin()
        return p.deferred

    def _endProcess(self, reason, p):
        self.failIf(reason.check(error.ProcessDone),
                    'Child should fail due to EPIPE.')
        reason.trap(error.ProcessTerminated)
        # child must not get past that write without raising
        self.failIfEqual(reason.value.exitCode, 42,
                         'process reason was %r' % reason)
        self.failUnlessEqual(p.output, '')
        return p.errput

    def test_stdout(self):
        """ProcessProtocol.transport.closeStdout actually closes the pipe."""
        d = self.doit(1)
        def _check(errput):
            self.failIfEqual(errput.find('OSError'), -1)
            if runtime.platform.getType() != 'win32':
                self.failIfEqual(errput.find('Broken pipe'), -1)
        d.addCallback(_check)
        return d

    def test_stderr(self):
        """ProcessProtocol.transport.closeStderr actually closes the pipe."""
        d = self.doit(2)
        def _check(errput):
            # there should be no stderr open, so nothing for it to
            # write the error to.
            self.failUnlessEqual(errput, '')
        d.addCallback(_check)
        return d


skipMessage = "wrong platform or reactor doesn't support IReactorProcess"
if (runtime.platform.getType() != 'posix') or (not interfaces.IReactorProcess(reactor, None)):
    PosixProcessTestCase.skip = skipMessage
    PosixProcessTestCasePTY.skip = skipMessage
    TestTwoProcessesPosix.skip = skipMessage
    FDTest.skip = skipMessage
else:
    # do this before running the tests: it uses SIGCHLD and stuff internally
    lsOut = popen2.popen3("/bin/ls ZZXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")[2].read()

if (runtime.platform.getType() != 'win32') or (not interfaces.IReactorProcess(reactor, None)):
    Win32ProcessTestCase.skip = skipMessage
    TestTwoProcessesNonPosix.skip = skipMessage

if not interfaces.IReactorProcess(reactor, None):
    ProcessTestCase.skip = skipMessage
    ClosingPipes.skip = skipMessage
