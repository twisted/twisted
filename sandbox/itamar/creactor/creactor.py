"""C hooks from inside reactor."""

from twisted.internet import tcp

import tcp as ctcp

class CServer(ctcp._CMixin, tcp.Server):

    def __init__(self, *args, **kwargs):
        tcp.Server.__init__(self, *args, **kwargs)


tcp.Port.transport = CServer
