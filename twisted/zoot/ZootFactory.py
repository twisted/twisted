from twisted.internet.protocol import Factory, Protocol
from twisted.internet.app import Application
from twisted.protocols import gnutella

class ZootFactory(Factory):

    protocol = gnutella.GnutellaTalker

    def __init__(self):
        pass
