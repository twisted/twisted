# inital work at building a simpler interface to the Conchcode

import struct
from twisted.conch.ssh import common, transport, userauth, connection, keys
from twisted.conch.ssh import channel, session
from twisted.internet import defer, protocol, error
from twisted.python import failure

class SimpleTransport(transport.SSHClientTransport):

    def __init__(self, d):
        """
        d is a Deferred called back when the basic transport setup is done.
        it is called back with this object.
        """
        self._d = d
        self._authClient = None

    def verifyHostKey(self, hostKey, fingerprint):
        self._hostKey = hostKey
        self._fingerprint = fingerprint
        return defer.succeed(1)

    def connectionSecure(self):
        d = self._d
        del self._d
        d.callback(self)

    def _getAuthClient(self):
        d = defer.Deferred()
        self._conn = SimpleConnection()
        self._authClient = SimpleAuthClient(d, self._conn)
        self.requestService(self._authClient)
        return d

    # callable methods

    def getHostKey(self):
        """
        Called by the client to get the host key.

        Returns (keyType, keyData, fingerprint)
        """
        t, k = common.getNS(self._hostKey)
        return (t, self._hostKey, self._fingerprint)

    def isAuthenticated(self):
        """
        Returns True if we are authenticated, else False.
        """
        if not self._authClient: return False
        return self._authClient._authenticated 

    def authPassword(self, username, password):
        if not self._authClient:
            d = self._getAuthClient()
            d.addCallback(lambda x:self.authPassword(username, password))
        else:
            self._authClient.user = username
            d = self._authClient._d = defer.Deferred()
            self._authClient.getPassword = lambda:defer.succeed(password)
            self._authClient.tryAuth('password')
        return d

    def authPublicKey(self, username, privateKey):
        if not self._authClient:
            d = self._getAuthClient()
            d.addCallback(lambda x:self.authPublicKey(username, privateKey))
        else:
            self._authClient.user = username
            d = self._authClient._d = defer.Deferred()
            privObj = keys.getPrivateKeyObject(data=privateKey)
            pubKey = keys.makePublicKeyBlob(privObj)
            self._authClient.getPublicKey = lambda:pubKey
            self._authClient.getPrivateKey = lambda:defer.succeed(privObj)
            self._authClient.tryAuth('publickey')
        return d

    def openSession(self):
        d = defer.Deferred()
        c = SimpleSession(conn=self._conn)
        c._d = d
        self._conn.openChannel(c)
        return d

class SimpleAuthClient(userauth.SSHUserAuthClient):

    def __init__(self, d, instance):
        userauth.SSHUserAuthClient.__init__(self, None, instance)
        self._d = d
        self._authenticated = False

    def serviceStarted(self):
        d = self._d
        del self._d
        d.callback(None)

    def ssh_USERAUTH_SUCCESS(self, packet):
        d = self._d
        del self._d
        self.transport.setService(self.instance)
        self._authenticated = True
        self.ssh_USERAUTH_SUCCESS = lambda x: None
        d.callback(None)

    def ssh_USERAUTH_FAILURE(self, packet):
        canContinue, partial = common.getNS(packet)
        partial = ord(partial)
        if partial:
            d = self._d
            del self._d
            d.callback(None)
        else:
            d.errback(error.ConchError())

class SimpleConnection(connection.SSHConnection): pass

class SimpleSession(channel.SSHChannel):

    name = 'session'

    def channelOpen(self, data):
        d = self._d
        del self._d
        self.specificData = data
        d.callback(self)

    def openFailed(self, reason):
        d = self._d
        del self._d
        d.errback(reason)

    # client methods

    def setClient(self, client):
        if isinstance(client, protocol.ProcessProtocol):
            self.dataReceived = client.outReceived
            self.extReceived = client.errReceived
            self.eofReceived = client.inConnectionLost
            def _exit_status(status):
                code = struct.unpack('!L', status[:4])[0]
                if code == 0:
                    err = error.ProcessDone(None)
                else:
                    err = error.ProcessTerminated(code)
                client.processEnded(failure.Failure(err))
                return True
            self.request_exit_status = _exit_status
        else:
            self.dataReceived = client.dataReceived
            self.closed = lambda:client.connectionLost(protocol.connectionDone)
        client.makeConnection(self)

    def requestPTY(self, term='xterm', width=80, height=24, xpixel=0, ypixel=0, modes='', wantReply = 0):
        data = session.packRequest_pty_req(term, (width, heght, xpixel, ypixel), modes)
        return self.conn.sendRequest(self, 'pty-req', data, wantReply)

    def openShell(self, wantReply = 0):
        return self.conn.sendRequest(self, 'shell', '', wantReply)

    def openExec(self, program, wantReply = 0):
        return self.conn.sendRequest(self, 'exec', common.NS(program), wantReply)
        
