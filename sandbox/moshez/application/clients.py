from twisted.application import service

class _AbstractClient(service.Service):

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        if d.has_key('_connection'):
            del d['_connection']
        return d

    def startService(self):
        service.Service.startService(self)
        self._connection = self.getConnection()

    def stopService(self):
        service.Service.stopService(self)
        #self._connection.stopConnecting()

    def getConnection(self):
        from twisted.internet import reactor
        return getattr(reactor, self.method)(*self.args, **self.kwargs)


class GenericClient(_AbstractClient):
    method = 'connectWith'

class TCPClient(_AbstractClient):
    method = 'connectTCP'

class UNIXClient(_AbstractClient):
    method = 'connectUNIX'

class SSLClient(_AbstractClient):
    method = 'connectSSL'

class UDPClient(_AbstractClient):
    method = 'connectUDP'

class UNIXDatagramClient(_AbstractClient):
    method = 'connectUNIXDatagram'

class MulticastClient(_AbstractClient):
    method = 'connectMulticast'
