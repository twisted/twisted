from twisted.application import service


class _AbstracrServer(service.Service):

    privileged = 0

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __getstate__(self):
        d = service.Service.__getstate__(self)
        if d.has_key('_port'):
            del d['_port']
        return d

    def preStartService(self):
        service.Service.preStartService(self)
        if self.privileged:
            self._port = self.getPort()

    def startService(self):
        service.Service.startService(self)
        if not self.privileged:
            self._port = self.getPort()

    def stopService(self):
        service.Service.stopService(self)
        self._port.stopListening()

    def getPort(self):
        return getattr(reactor, self.method)(*self.args, **self.kwargs)


class GenericServer(_AbstractServer):
    method = 'listenWith'

class TCPServer(_AbstractServer):
    method = 'listenTCP'

class UNIXServer(_AbstractServer):
    method = 'listenUNIX'

class SSLServer(_AbstractServer):
    method = 'listenSSL'

class UDPServer(_AbstractServer):
    method = 'listenUDP'

class UNIXDatagramServer(_AbstractServer):
    method = 'listenUNIXDatagram'

class MulticastServer(_AbstractServer):
    method = 'listenMulticast'
