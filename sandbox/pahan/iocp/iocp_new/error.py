from twisted.internet.error import CannotListenError

class GenCannonListenError(CannotListenError):
    """I do not discriminate against non-INET addresses"""
    def __init__(self, address, socketError):
        self.address = address
        self.socketError = socketError

    def __str__(self):
        return "Couldn't listen on %s: %s." % (address, self.port,
                                                 self.socketError)

