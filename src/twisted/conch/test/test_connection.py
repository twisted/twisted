# Copyright (c) 2007-2010 Twisted Matrix Laboratories.
# See LICENSE for details

"""
This module tests twisted.conch.ssh.connection.
"""

import struct

from twisted.conch import error
from twisted.conch.ssh import channel, common, connection
from twisted.trial import unittest
from twisted.conch.test import test_userauth


class TestChannel(channel.SSHChannel):
    """
    A mocked-up version of twisted.conch.ssh.channel.SSHChannel.

    @ivar gotOpen: True if channelOpen has been called.
    @type gotOpen: C{bool}
    @ivar specificData: the specific channel open data passed to channelOpen.
    @type specificData: C{str}
    @ivar openFailureReason: the reason passed to openFailed.
    @type openFailed: C{error.ConchError}
    @ivar inBuffer: a C{list} of strings received by the channel.
    @type inBuffer: C{list}
    @ivar extBuffer: a C{list} of 2-tuples (type, extended data) of received by
        the channel.
    @type extBuffer: C{list}
    @ivar numberRequests: the number of requests that have been made to this
        channel.
    @type numberRequests: C{int}
    @ivar gotEOF: True if the other side sent EOF.
    @type gotEOF: C{bool}
    @ivar gotOneClose: True if the other side closed the connection.
    @type gotOneClose: C{bool}
    @ivar gotClosed: True if the channel is closed.
    @type gotClosed: C{bool}
    """
    name = "TestChannel"
    gotOpen = False

    def logPrefix(self):
        return "TestChannel %i" % self.id

    def channelOpen(self, specificData):
        """
        The channel is open.  Set up the instance variables.
        """
        self.gotOpen = True
        self.specificData = specificData
        self.inBuffer = []
        self.extBuffer = []
        self.numberRequests = 0
        self.gotEOF = False
        self.gotOneClose = False
        self.gotClosed = False

    def openFailed(self, reason):
        """
        Opening the channel failed.  Store the reason why.
        """
        self.openFailureReason = reason

    def request_test(self, data):
        """
        A test request.  Return True if data is 'data'.

        @type data: C{str}
        """
        self.numberRequests += 1
        return data == 'data'

    def dataReceived(self, data):
        """
        Data was received.  Store it in the buffer.
        """
        self.inBuffer.append(data)

    def extReceived(self, code, data):
        """
        Extended data was received.  Store it in the buffer.
        """
        self.extBuffer.append((code, data))

    def eofReceived(self):
        """
        EOF was received.  Remember it.
        """
        self.gotEOF = True

    def closeReceived(self):
        """
        Close was received.  Remember it.
        """
        self.gotOneClose = True

    def closed(self):
        """
        The channel is closed.  Rembember it.
        """
        self.gotClosed = True

class TestAvatar:
    """
    A mocked-up version of twisted.conch.avatar.ConchUser
    """
    _ARGS_ERROR_CODE = 123

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        """
        The server wants us to return a channel.  If the requested channel is
        our TestChannel, return it, otherwise return None.
        """
        if channelType == TestChannel.name:
            return TestChannel(remoteWindow=windowSize,
                    remoteMaxPacket=maxPacket,
                    data=data, avatar=self)
        elif channelType == "conch-error-args":
            # Raise a ConchError with backwards arguments to make sure the
            # connection fixes it for us.  This case should be deprecated and
            # deleted eventually, but only after all of Conch gets the argument
            # order right.
            raise error.ConchError(
                self._ARGS_ERROR_CODE, "error args in wrong order")


    def gotGlobalRequest(self, requestType, data):
        """
        The client has made a global request.  If the global request is
        'TestGlobal', return True.  If the global request is 'TestData',
        return True and the request-specific data we received.  Otherwise,
        return False.
        """
        if requestType == 'TestGlobal':
            return True
        elif requestType == 'TestData':
            return True, data
        else:
            return False



class TestConnection(connection.SSHConnection):
    """
    A subclass of SSHConnection for testing.

    @ivar channel: the current channel.
    @type channel. C{TestChannel}
    """

    def logPrefix(self):
        return "TestConnection"

    def global_TestGlobal(self, data):
        """
        The other side made the 'TestGlobal' global request.  Return True.
        """
        return True

    def global_Test_Data(self, data):
        """
        The other side made the 'Test-Data' global request.  Return True and
        the data we received.
        """
        return True, data

    def channel_TestChannel(self, windowSize, maxPacket, data):
        """
        The other side is requesting the TestChannel.  Create a C{TestChannel}
        instance, store it, and return it.
        """
        self.channel = TestChannel(remoteWindow=windowSize,
                remoteMaxPacket=maxPacket, data=data)
        return self.channel

    def channel_ErrorChannel(self, windowSize, maxPacket, data):
        """
        The other side is requesting the ErrorChannel.  Raise an exception.
        """
        raise AssertionError('no such thing')



class ConnectionTests(unittest.TestCase):

    if test_userauth.transport is None:
        skip = "Cannot run without both cryptography and pyasn1"

    def setUp(self):
        self.transport = test_userauth.FakeTransport(None)
        self.transport.avatar = TestAvatar()
        self.conn = TestConnection()
        self.conn.transport = self.transport
        self.conn.serviceStarted()

    def _openChannel(self, channel):
        """
        Open the channel with the default connection.
        """
        self.conn.openChannel(channel)
        self.transport.packets = self.transport.packets[:-1]
        self.conn.ssh_CHANNEL_OPEN_CONFIRMATION(struct.pack('>2L',
            channel.id, 255) + '\x00\x02\x00\x00\x00\x00\x80\x00')

    def tearDown(self):
        self.conn.serviceStopped()

    def test_linkAvatar(self):
        """
        Test that the connection links itself to the avatar in the
        transport.
        """
        self.assertIs(self.transport.avatar.conn, self.conn)

    def test_serviceStopped(self):
        """
        Test that serviceStopped() closes any open channels.
        """
        channel1 = TestChannel()
        channel2 = TestChannel()
        self.conn.openChannel(channel1)
        self.conn.openChannel(channel2)
        self.conn.ssh_CHANNEL_OPEN_CONFIRMATION('\x00\x00\x00\x00' * 4)
        self.assertTrue(channel1.gotOpen)
        self.assertFalse(channel2.gotOpen)
        self.conn.serviceStopped()
        self.assertTrue(channel1.gotClosed)

    def test_GLOBAL_REQUEST(self):
        """
        Test that global request packets are dispatched to the global_*
        methods and the return values are translated into success or failure
        messages.
        """
        self.conn.ssh_GLOBAL_REQUEST(common.NS('TestGlobal') + '\xff')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_REQUEST_SUCCESS, '')])
        self.transport.packets = []
        self.conn.ssh_GLOBAL_REQUEST(common.NS('TestData') + '\xff' +
                'test data')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_REQUEST_SUCCESS, 'test data')])
        self.transport.packets = []
        self.conn.ssh_GLOBAL_REQUEST(common.NS('TestBad') + '\xff')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_REQUEST_FAILURE, '')])
        self.transport.packets = []
        self.conn.ssh_GLOBAL_REQUEST(common.NS('TestGlobal') + '\x00')
        self.assertEqual(self.transport.packets, [])

    def test_REQUEST_SUCCESS(self):
        """
        Test that global request success packets cause the Deferred to be
        called back.
        """
        d = self.conn.sendGlobalRequest('request', 'data', True)
        self.conn.ssh_REQUEST_SUCCESS('data')
        def check(data):
            self.assertEqual(data, 'data')
        d.addCallback(check)
        d.addErrback(self.fail)
        return d

    def test_REQUEST_FAILURE(self):
        """
        Test that global request failure packets cause the Deferred to be
        erred back.
        """
        d = self.conn.sendGlobalRequest('request', 'data', True)
        self.conn.ssh_REQUEST_FAILURE('data')
        def check(f):
            self.assertEqual(f.value.data, 'data')
        d.addCallback(self.fail)
        d.addErrback(check)
        return d

    def test_CHANNEL_OPEN(self):
        """
        Test that open channel packets cause a channel to be created and
        opened or a failure message to be returned.
        """
        del self.transport.avatar
        self.conn.ssh_CHANNEL_OPEN(common.NS('TestChannel') +
                '\x00\x00\x00\x01' * 4)
        self.assertTrue(self.conn.channel.gotOpen)
        self.assertEqual(self.conn.channel.conn, self.conn)
        self.assertEqual(self.conn.channel.data, '\x00\x00\x00\x01')
        self.assertEqual(self.conn.channel.specificData, '\x00\x00\x00\x01')
        self.assertEqual(self.conn.channel.remoteWindowLeft, 1)
        self.assertEqual(self.conn.channel.remoteMaxPacket, 1)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_OPEN_CONFIRMATION,
                    '\x00\x00\x00\x01\x00\x00\x00\x00\x00\x02\x00\x00'
                    '\x00\x00\x80\x00')])
        self.transport.packets = []
        self.conn.ssh_CHANNEL_OPEN(common.NS('BadChannel') +
                '\x00\x00\x00\x02' * 4)
        self.flushLoggedErrors()
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_OPEN_FAILURE,
                    '\x00\x00\x00\x02\x00\x00\x00\x03' + common.NS(
                    'unknown channel') + common.NS(''))])
        self.transport.packets = []
        self.conn.ssh_CHANNEL_OPEN(common.NS('ErrorChannel') +
                '\x00\x00\x00\x02' * 4)
        self.flushLoggedErrors()
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_OPEN_FAILURE,
                    '\x00\x00\x00\x02\x00\x00\x00\x02' + common.NS(
                    'unknown failure') + common.NS(''))])


    def _lookupChannelErrorTest(self, code):
        """
        Deliver a request for a channel open which will result in an exception
        being raised during channel lookup.  Assert that an error response is
        delivered as a result.
        """
        self.transport.avatar._ARGS_ERROR_CODE = code
        self.conn.ssh_CHANNEL_OPEN(
            common.NS('conch-error-args') + '\x00\x00\x00\x01' * 4)
        errors = self.flushLoggedErrors(error.ConchError)
        self.assertEqual(
            len(errors), 1, "Expected one error, got: %r" % (errors,))
        self.assertEqual(errors[0].value.args, (123, "error args in wrong order"))
        self.assertEqual(
            self.transport.packets,
            [(connection.MSG_CHANNEL_OPEN_FAILURE,
              # The response includes some bytes which identifying the
              # associated request, as well as the error code (7b in hex) and
              # the error message.
              '\x00\x00\x00\x01\x00\x00\x00\x7b' + common.NS(
                        'error args in wrong order') + common.NS(''))])


    def test_lookupChannelError(self):
        """
        If a C{lookupChannel} implementation raises L{error.ConchError} with the
        arguments in the wrong order, a C{MSG_CHANNEL_OPEN} failure is still
        sent in response to the message.

        This is a temporary work-around until L{error.ConchError} is given
        better attributes and all of the Conch code starts constructing
        instances of it properly.  Eventually this functionality should be
        deprecated and then removed.
        """
        self._lookupChannelErrorTest(123)


    def test_lookupChannelErrorLongCode(self):
        """
        Like L{test_lookupChannelError}, but for the case where the failure code
        is represented as a C{long} instead of a C{int}.
        """
        self._lookupChannelErrorTest(123L)


    def test_CHANNEL_OPEN_CONFIRMATION(self):
        """
        Test that channel open confirmation packets cause the channel to be
        notified that it's open.
        """
        channel = TestChannel()
        self.conn.openChannel(channel)
        self.conn.ssh_CHANNEL_OPEN_CONFIRMATION('\x00\x00\x00\x00'*5)
        self.assertEqual(channel.remoteWindowLeft, 0)
        self.assertEqual(channel.remoteMaxPacket, 0)
        self.assertEqual(channel.specificData, '\x00\x00\x00\x00')
        self.assertEqual(self.conn.channelsToRemoteChannel[channel],
                0)
        self.assertEqual(self.conn.localToRemoteChannel[0], 0)

    def test_CHANNEL_OPEN_FAILURE(self):
        """
        Test that channel open failure packets cause the channel to be
        notified that its opening failed.
        """
        channel = TestChannel()
        self.conn.openChannel(channel)
        self.conn.ssh_CHANNEL_OPEN_FAILURE('\x00\x00\x00\x00\x00\x00\x00'
                '\x01' + common.NS('failure!'))
        self.assertEqual(channel.openFailureReason.args, ('failure!', 1))
        self.assertEqual(self.conn.channels.get(channel), None)


    def test_CHANNEL_WINDOW_ADJUST(self):
        """
        Test that channel window adjust messages add bytes to the channel
        window.
        """
        channel = TestChannel()
        self._openChannel(channel)
        oldWindowSize = channel.remoteWindowLeft
        self.conn.ssh_CHANNEL_WINDOW_ADJUST('\x00\x00\x00\x00\x00\x00\x00'
                '\x01')
        self.assertEqual(channel.remoteWindowLeft, oldWindowSize + 1)

    def test_CHANNEL_DATA(self):
        """
        Test that channel data messages are passed up to the channel, or
        cause the channel to be closed if the data is too large.
        """
        channel = TestChannel(localWindow=6, localMaxPacket=5)
        self._openChannel(channel)
        self.conn.ssh_CHANNEL_DATA('\x00\x00\x00\x00' + common.NS('data'))
        self.assertEqual(channel.inBuffer, ['data'])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_WINDOW_ADJUST, '\x00\x00\x00\xff'
                    '\x00\x00\x00\x04')])
        self.transport.packets = []
        longData = 'a' * (channel.localWindowLeft + 1)
        self.conn.ssh_CHANNEL_DATA('\x00\x00\x00\x00' + common.NS(longData))
        self.assertEqual(channel.inBuffer, ['data'])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])
        channel = TestChannel()
        self._openChannel(channel)
        bigData = 'a' * (channel.localMaxPacket + 1)
        self.transport.packets = []
        self.conn.ssh_CHANNEL_DATA('\x00\x00\x00\x01' + common.NS(bigData))
        self.assertEqual(channel.inBuffer, [])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])

    def test_CHANNEL_EXTENDED_DATA(self):
        """
        Test that channel extended data messages are passed up to the channel,
        or cause the channel to be closed if they're too big.
        """
        channel = TestChannel(localWindow=6, localMaxPacket=5)
        self._openChannel(channel)
        self.conn.ssh_CHANNEL_EXTENDED_DATA('\x00\x00\x00\x00\x00\x00\x00'
                                            '\x00' + common.NS('data'))
        self.assertEqual(channel.extBuffer, [(0, 'data')])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_WINDOW_ADJUST, '\x00\x00\x00\xff'
                    '\x00\x00\x00\x04')])
        self.transport.packets = []
        longData = 'a' * (channel.localWindowLeft + 1)
        self.conn.ssh_CHANNEL_EXTENDED_DATA('\x00\x00\x00\x00\x00\x00\x00'
                                            '\x00' + common.NS(longData))
        self.assertEqual(channel.extBuffer, [(0, 'data')])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])
        channel = TestChannel()
        self._openChannel(channel)
        bigData = 'a' * (channel.localMaxPacket + 1)
        self.transport.packets = []
        self.conn.ssh_CHANNEL_EXTENDED_DATA('\x00\x00\x00\x01\x00\x00\x00'
                                            '\x00' + common.NS(bigData))
        self.assertEqual(channel.extBuffer, [])
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])

    def test_CHANNEL_EOF(self):
        """
        Test that channel eof messages are passed up to the channel.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.ssh_CHANNEL_EOF('\x00\x00\x00\x00')
        self.assertTrue(channel.gotEOF)

    def test_CHANNEL_CLOSE(self):
        """
        Test that channel close messages are passed up to the channel.  Also,
        test that channel.close() is called if both sides are closed when this
        message is received.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.sendClose(channel)
        self.conn.ssh_CHANNEL_CLOSE('\x00\x00\x00\x00')
        self.assertTrue(channel.gotOneClose)
        self.assertTrue(channel.gotClosed)

    def test_CHANNEL_REQUEST_success(self):
        """
        Test that channel requests that succeed send MSG_CHANNEL_SUCCESS.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.ssh_CHANNEL_REQUEST('\x00\x00\x00\x00' + common.NS('test')
                + '\x00')
        self.assertEqual(channel.numberRequests, 1)
        d = self.conn.ssh_CHANNEL_REQUEST('\x00\x00\x00\x00' + common.NS(
            'test') + '\xff' + 'data')
        def check(result):
            self.assertEqual(self.transport.packets,
                    [(connection.MSG_CHANNEL_SUCCESS, '\x00\x00\x00\xff')])
        d.addCallback(check)
        return d

    def test_CHANNEL_REQUEST_failure(self):
        """
        Test that channel requests that fail send MSG_CHANNEL_FAILURE.
        """
        channel = TestChannel()
        self._openChannel(channel)
        d = self.conn.ssh_CHANNEL_REQUEST('\x00\x00\x00\x00' + common.NS(
            'test') + '\xff')
        def check(result):
            self.assertEqual(self.transport.packets,
                    [(connection.MSG_CHANNEL_FAILURE, '\x00\x00\x00\xff'
                        )])
        d.addCallback(self.fail)
        d.addErrback(check)
        return d

    def test_CHANNEL_REQUEST_SUCCESS(self):
        """
        Test that channel request success messages cause the Deferred to be
        called back.
        """
        channel = TestChannel()
        self._openChannel(channel)
        d = self.conn.sendRequest(channel, 'test', 'data', True)
        self.conn.ssh_CHANNEL_SUCCESS('\x00\x00\x00\x00')
        def check(result):
            self.assertTrue(result)
        return d

    def test_CHANNEL_REQUEST_FAILURE(self):
        """
        Test that channel request failure messages cause the Deferred to be
        erred back.
        """
        channel = TestChannel()
        self._openChannel(channel)
        d = self.conn.sendRequest(channel, 'test', '', True)
        self.conn.ssh_CHANNEL_FAILURE('\x00\x00\x00\x00')
        def check(result):
            self.assertEqual(result.value.value, 'channel request failed')
        d.addCallback(self.fail)
        d.addErrback(check)
        return d

    def test_sendGlobalRequest(self):
        """
        Test that global request messages are sent in the right format.
        """
        d = self.conn.sendGlobalRequest('wantReply', 'data', True)
        # must be added to prevent errbacking during teardown
        d.addErrback(lambda failure: None)
        self.conn.sendGlobalRequest('noReply', '', False)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_GLOBAL_REQUEST, common.NS('wantReply') +
                    '\xffdata'),
                 (connection.MSG_GLOBAL_REQUEST, common.NS('noReply') +
                     '\x00')])
        self.assertEqual(self.conn.deferreds, {'global':[d]})

    def test_openChannel(self):
        """
        Test that open channel messages are sent in the right format.
        """
        channel = TestChannel()
        self.conn.openChannel(channel, 'aaaa')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_OPEN, common.NS('TestChannel') +
                    '\x00\x00\x00\x00\x00\x02\x00\x00\x00\x00\x80\x00aaaa')])
        self.assertEqual(channel.id, 0)
        self.assertEqual(self.conn.localChannelID, 1)

    def test_sendRequest(self):
        """
        Test that channel request messages are sent in the right format.
        """
        channel = TestChannel()
        self._openChannel(channel)
        d = self.conn.sendRequest(channel, 'test', 'test', True)
        # needed to prevent errbacks during teardown.
        d.addErrback(lambda failure: None)
        self.conn.sendRequest(channel, 'test2', '', False)
        channel.localClosed = True # emulate sending a close message
        self.conn.sendRequest(channel, 'test3', '', True)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_REQUEST, '\x00\x00\x00\xff' +
                    common.NS('test') + '\x01test'),
                 (connection.MSG_CHANNEL_REQUEST, '\x00\x00\x00\xff' +
                     common.NS('test2') + '\x00')])
        self.assertEqual(self.conn.deferreds[0], [d])

    def test_adjustWindow(self):
        """
        Test that channel window adjust messages cause bytes to be added
        to the window.
        """
        channel = TestChannel(localWindow=5)
        self._openChannel(channel)
        channel.localWindowLeft = 0
        self.conn.adjustWindow(channel, 1)
        self.assertEqual(channel.localWindowLeft, 1)
        channel.localClosed = True
        self.conn.adjustWindow(channel, 2)
        self.assertEqual(channel.localWindowLeft, 1)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_WINDOW_ADJUST, '\x00\x00\x00\xff'
                    '\x00\x00\x00\x01')])

    def test_sendData(self):
        """
        Test that channel data messages are sent in the right format.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.sendData(channel, 'a')
        channel.localClosed = True
        self.conn.sendData(channel, 'b')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_DATA, '\x00\x00\x00\xff' +
                    common.NS('a'))])

    def test_sendExtendedData(self):
        """
        Test that channel extended data messages are sent in the right format.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.sendExtendedData(channel, 1, 'test')
        channel.localClosed = True
        self.conn.sendExtendedData(channel, 2, 'test2')
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_EXTENDED_DATA, '\x00\x00\x00\xff' +
                    '\x00\x00\x00\x01' + common.NS('test'))])

    def test_sendEOF(self):
        """
        Test that channel EOF messages are sent in the right format.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.sendEOF(channel)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_EOF, '\x00\x00\x00\xff')])
        channel.localClosed = True
        self.conn.sendEOF(channel)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_EOF, '\x00\x00\x00\xff')])

    def test_sendClose(self):
        """
        Test that channel close messages are sent in the right format.
        """
        channel = TestChannel()
        self._openChannel(channel)
        self.conn.sendClose(channel)
        self.assertTrue(channel.localClosed)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])
        self.conn.sendClose(channel)
        self.assertEqual(self.transport.packets,
                [(connection.MSG_CHANNEL_CLOSE, '\x00\x00\x00\xff')])

        channel2 = TestChannel()
        self._openChannel(channel2)
        channel2.remoteClosed = True
        self.conn.sendClose(channel2)
        self.assertTrue(channel2.gotClosed)

    def test_getChannelWithAvatar(self):
        """
        Test that getChannel dispatches to the avatar when an avatar is
        present. Correct functioning without the avatar is verified in
        test_CHANNEL_OPEN.
        """
        channel = self.conn.getChannel('TestChannel', 50, 30, 'data')
        self.assertEqual(channel.data, 'data')
        self.assertEqual(channel.remoteWindowLeft, 50)
        self.assertEqual(channel.remoteMaxPacket, 30)
        self.assertRaises(error.ConchError, self.conn.getChannel,
                'BadChannel', 50, 30, 'data')

    def test_gotGlobalRequestWithoutAvatar(self):
        """
        Test that gotGlobalRequests dispatches to global_* without an avatar.
        """
        del self.transport.avatar
        self.assertTrue(self.conn.gotGlobalRequest('TestGlobal', 'data'))
        self.assertEqual(self.conn.gotGlobalRequest('Test-Data', 'data'),
                (True, 'data'))
        self.assertFalse(self.conn.gotGlobalRequest('BadGlobal', 'data'))


    def test_channelClosedCausesLeftoverChannelDeferredsToErrback(self):
        """
        Whenever an SSH channel gets closed any Deferred that was returned by a
        sendRequest() on its parent connection must be errbacked.
        """
        channel = TestChannel()
        self._openChannel(channel)

        d = self.conn.sendRequest(
            channel, "dummyrequest", "dummydata", wantReply=1)
        d = self.assertFailure(d, error.ConchError)
        self.conn.channelClosed(channel)
        return d



class CleanConnectionShutdownTests(unittest.TestCase):
    """
    Check whether correct cleanup is performed on connection shutdown.
    """
    if test_userauth.transport is None:
        skip = "Cannot run without both cryptography and pyasn1"

    def setUp(self):
        self.transport = test_userauth.FakeTransport(None)
        self.transport.avatar = TestAvatar()
        self.conn = TestConnection()
        self.conn.transport = self.transport


    def test_serviceStoppedCausesLeftoverGlobalDeferredsToErrback(self):
        """
        Once the service is stopped any leftover global deferred returned by
        a sendGlobalRequest() call must be errbacked.
        """
        self.conn.serviceStarted()

        d = self.conn.sendGlobalRequest(
            "dummyrequest", "dummydata", wantReply=1)
        d = self.assertFailure(d, error.ConchError)
        self.conn.serviceStopped()
        return d


