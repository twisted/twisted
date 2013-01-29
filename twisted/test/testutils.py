# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
I{Private} test utilities for use throughout Twisted's test suite.  Unlike
C{proto_helpers}, this is no exception to the
don't-use-it-outside-Twisted-we-won't-maintain-compatibility rule!

@note: Maintainers be aware: things in this module should be gradually promoted
    to more full-featured test helpers and exposed as public API as your
    maintenance time permits.  In order to be public API though, they need
    their own test cases.
"""

from cStringIO import StringIO

from xml.dom import minidom as dom

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



class XMLAssertionMixin(object):
    """
    Test mixin defining a method for comparing serialized XML documents.

    Must be mixed in to a L{test case<unittest.TestCase>}.
    """

    def assertXMLEqual(self, first, second):
        """
        Verify that two strings represent the same XML document.

        @param first: An XML string.
        @type first: L{bytes}

        @param second: An XML string that should match C{first}.
        @type second: L{bytes}
        """
        self.assertEqual(
            dom.parseString(first).toxml(),
            dom.parseString(second).toxml())


