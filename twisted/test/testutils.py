from cStringIO import StringIO
from twisted.internet.protocol import FileWrapper

class IOPump:
    """Utility to pump data between clients and servers for protocol testing.

    Perhaps this is a utility worthy of being in protocol.py?
    """
    def __init__(self, client, server, clientIO, serverIO):
        self.client = client
        self.server = server
        self.clientIO = clientIO
        self.serverIO = serverIO

    def flush(self):
        "Pump until there is no more input or output."
        while self.pump():
            pass

    def pump(self):
        """Move data back and forth.

        Returns whether any data was moved.
        """
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        cData = self.clientIO.read()
        sData = self.serverIO.read()
        self.clientIO.seek(0)
        self.serverIO.seek(0)
        self.clientIO.truncate()
        self.serverIO.truncate()
        for byte in cData:
            self.server.dataReceived(byte)
        for byte in sData:
            self.client.dataReceived(byte)
        if cData or sData:
            return 1
        else:
            return 0


def returnConnected(server, client):
    """Take two Protocol instances and connect them.
    """
    cio = StringIO()
    sio = StringIO()
    client.makeConnection(FileWrapper(cio))
    server.makeConnection(FileWrapper(sio))
    pump = IOPump(client, server, cio, sio)
    # Challenge-response authentication:
    pump.flush()
    # Uh...
    pump.flush()
    return pump
