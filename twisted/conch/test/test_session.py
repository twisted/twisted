# Copyright (c) 2009 Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for the 'session' channel implementation in twisted.conch.ssh.session.

See also RFC 4254.
"""

import signal
import struct
import sys
import os

from twisted.conch.ssh.session import SSHSession, SSHSessionProcessProtocol
from twisted.conch.ssh.session import SUPPORTED_SIGNALS
from twisted.conch.ssh.common import NS

from twisted.internet.defer import succeed
from twisted.internet.error import ProcessTerminated, ProcessDone
from twisted.python.failure import Failure

from twisted.trial.unittest import TestCase



class StubConnection(object):
    """
    A stub for twisted.conch.ssh.connection.SSHConnection.  Record the data
    that channels send, and when they try to close the connection.

    @ivar data: a C{dict} mapping C{SSHChannel}s to a C{list} of C{str} of data
        they sent.
    @ivar extData: a C{dict} mapping L{SSHChannel}s to a C{list} of C{tuple} of
        (C{int}, C{str}) of extended data they sent.
    @ivar requests: a C{dict} mapping L{SSHChannel}s to a C{list} of C{tuple}
        of (C{str}, C{str}) of channel requests they made.
    @ivar eofs: a C{dict} mapping L{SSHChannel}s to C{true} if they have sent
        an EOF.
    @ivar closes: a C{dict} mapping L{SSHChannel}s to C{true} if they have sent
        a close.
    """


    def __init__(self):
        """
        Initialize our instance variables.
        """
        self.data = {}
        self.extData = {}
        self.requests = {}
        self.eofs = {}
        self.closes = {}


    def logPrefix(self):
        """
        Return our logging prefix.
        """
        return "MockConnection"


    def sendData(self, channel, data):
        """
        Record the sent data.
        """
        self.data.setdefault(channel, []).append(data)


    def sendExtendedData(self, channel, type, data):
        """
        Record the sent extended data.
        """
        self.extData.setdefault(channel, []).append((type, data))


    def sendRequest(self, channel, request, data, wantReply=False):
        """
        Record the sent channel request.
        """
        self.requests.setdefault(channel, []).append((request, data,
            wantReply))
        if wantReply:
            return succeed(None)


    def sendEOF(self, channel):
        """
        Record the sent EOF.
        """
        self.eofs[channel] = True


    def sendClose(self, channel):
        """
        Record the sent close.
        """
        self.closes[channel] = True



class SSHSessionProcessProtocolTestCase(TestCase):
    """
    Tests for L{SSHSessionProcessProtocol}.
    """

    def setUp(self):
        self.session = SSHSession(
            conn=StubConnection(), remoteWindow=500, remoteMaxPacket=100)
        self.pp = SSHSessionProcessProtocol(self.session)


    def assertSessionClosed(self):
        """
        Assert that C{self.session} is closed.
        """
        self.assertTrue(self.session.conn.closes[self.session])


    def assertRequestsEqual(self, expectedRequests):
        """
        Assert that C{self.session} has sent the C{expectedRequests}.
        """
        self.assertEqual(
            self.session.conn.requests[self.session],
            expectedRequests)


    def test_getSignalName(self):
        """
        _getSignalName should return the name of a signal when given the
        signal number.
        """
        for signalName in SUPPORTED_SIGNALS:
            signalName = 'SIG' + signalName
            signalValue = getattr(signal, signalName)
            sshName = self.pp._getSignalName(signalValue)
            self.assertEquals(sshName, signalName,
                              "%i: %s != %s" % (signalValue, sshName,
                                                signalName))


    def test_getSignalNameWithLocalSignal(self):
        """
        If there are signals in the signal module which aren't in the SSH RFC,
        we map their name to [signal name]@[platform].
        """
        signal.SIGTwistedTest = signal.NSIG + 1 # value can't exist normally
        # Force reinitialization of signals
        self.pp._signalValuesToNames = None
        self.assertEquals(self.pp._getSignalName(signal.SIGTwistedTest),
                          'SIGTwistedTest@' + sys.platform)


    if getattr(signal, 'SIGALRM', None) is None:
        test_getSignalName.skip = test_getSignalNameWithLocalSignal.skip = \
            "Not all signals available"


    def test_processEndedWithExitCode(self):
        """
        When processEnded is called, if there is an exit code in the reason
        it should be sent in an exit-status method.  The connection should be
        closed.
        """
        self.pp.processEnded(Failure(ProcessDone(None)))
        self.assertRequestsEqual(
            [('exit-status', struct.pack('>I', 0) , False)])
        self.assertSessionClosed()


    def test_processEndedWithExitSignalCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the reason
        it should be sent in an exit-signal message.  The connection should be
        closed.
        """
        self.pp.processEnded(
            Failure(ProcessTerminated(1,
                signal.SIGTERM, 1 << 7))) # 7th bit means core dumped
        self.assertRequestsEqual(
            [('exit-signal',
              NS('TERM') # signal name
              + '\x01' # core dumped is true
              + NS('') # error message
              + NS(''), # language tag
              False)])
        self.assertSessionClosed()


    def test_processEndedWithExitSignalNoCoreDump(self):
        """
        When processEnded is called, if there is an exit signal in the
        reason it should be sent in an exit-signal message.  If no
        core was dumped, don't set the core-dump bit.
        """
        self.pp.processEnded(
            Failure(ProcessTerminated(1, signal.SIGTERM, 0)))
        # see comments in test_processEndedWithExitSignalCoreDump for the
        # meaning of the parts in the request
        self.assertRequestsEqual(
             [('exit-signal', NS('TERM') + '\x00' + NS('') + NS(''), False)])
        self.assertSessionClosed()


    if getattr(os, 'WCOREDUMP', None) is None:
        skipMsg = "can't run this w/o os.WCOREDUMP"
        test_processEndedWithExitSignalCoreDump.skip = skipMsg
        test_processEndedWithExitSignalNoCoreDump.skip = skipMsg
