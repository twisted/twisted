class Proactor(PosixReactorBase):
    # are these necessary?
    def registerHandler(self, handle, handler):
        self.completables[handle] = handler

    def unregisterHandler(self, handle):
        del self.completables[handle]

    # or notify one-by-one?

# async op does:
# issue with user defined parameters
# TODO: how is this handled on the ITransport level?
# ugh extra object creation overhead omfg (these are deferreds, not reusable, but perhaps make them so)
# write callbacks with bytes written
# read callbacks with (bytes_read, dict_of_optional_data), for example recvfrom address or ancillary crud

class AsyncOp(Deferred):
    def initiateOp(self):
        raise NotImplementedError

class OverlappedOp(AsyncOp):
    def __init__(self, *a, **kw):
        self.ov = OVERLAPPED()
        self.ov.object = "ovDone"

    def ovDone(self, ret, bytes):
        from twisted.internet import reactor
        reactor.unregisterHandler(self.handle)
        del self.handle
        del self.buffer
        # TODO: errback if ret is not good, for example cancelled
        self.callback(bytes)

class ReadFileOp(OverlappedOp)
    def initiateOp(self, handle, buffer):
        self.buffer = buffer # save a reference so that things don't blow up
        self.handle = handle
        # XXX: is this expensive to do? is this circular referring dangerous?
        from twisted.internet import reactor
        reactor.registerHandler(handle, self)
        (ret, bytes) = ReadFile(handle, buffer, self.ov)
        # TODO: need try-except block to at least cleanup self.handle/self.buffer and unregisterFile

