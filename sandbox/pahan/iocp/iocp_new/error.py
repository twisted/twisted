from twisted.internet import error

class CannotListenError(error.CannotListenError):
    """I do not discriminate against non-INET addresses"""
    def __init__(self, address, socketError):
        self.address = address
        self.socketError = socketError

    def __str__(self):
        return "Couldn't listen on %s: %s." % (self.address, self.socketError)

class IOCPException(Exception):
    pass

class HandleClosedException(IOCPException):
    pass

class NonFatalException(IOCPException):
    pass

class OperationCancelledException(IOCPException):
    pass

class UnknownException(IOCPException):
    pass

ERROR_NOT_ENOUGH_MEMORY = 8
ERROR_NETNAME_DELETED = 64
ERROR_OPERATION_ABORTED = 995
ERROR_CONNECTION_REFUSED = 1225
ERROR_PORT_UNREACHABLE = 1234
ERROR_CONNECTION_ABORTED = 1236
ERROR_INVALID_USER_BUFFER = 1784

