from twisted.internet import default
import event

class LibeventReactor(default.PosixReactorBase):
    _queue = _readWriteEvents = _signalEvents = None

    def __init__(self):
        base.ReactorBase.__init__(self)
        self._queue = []
        self._readWriteEvents = {}
        self._signalEvents = {}

    def doIteration(self):
        event.loop()
        for obj, meth in self._queue:
            getattr(obj, meth)()

    def _cbReader(self, reader):
        self._queue.append((reader, 'doRead'))
        return 1 # persist event until removed

    def _cbWriter(self, writer):
        self._queue.append((writer, 'doWrite'))
        return 1

    def addReader(self, reader):
        ev = event.Read(reader.fileno(), _cbReader, reader)
        # should probably check to see if it already exists
        self._readWriteEvents[reader] = ev

    def addWriter(self, writer):
        event.Write(writer.fileno(), _cbWriter, writer)
        self._readWriteEvents[writer] = ev

    def _removeEvent(self, k):
        ev = self._readWriteEvents.pop(k)
        ev.delete()

    def removeReader(self, reader):
        self._removeEvent(reader)

    def removeWriter(self, writer):
        self._removeEvent(writer)

    def removeAll(self):
        selectables = []
        for k, ev in self._readWriteEvents.iteritems():
            selectables.append(k)
            ev.delete()
        return selectables

    def _handleSignals(self):
        from twisted.python.runtime import platformType
        import signal
        if signal.getsignal(signal.SIGINT) == signal.default_int_handler:
            self._signalEvents[signal.SIGINT] = event.Signal(signal.SIGINT, self.sigInt)

        self._signalEvents[signal.SIGTERM] = event.Signal(signal.SIGTERM, self.sigTerm)

        if hasattr(signal, "SIGBREAK"):
            self._signalEvents[signal.SIGBREAK] = event.Signal(signal.SIGBREAK, self.sigBreak)

        if platformType = 'posix':
            self._signalEvents[signal.SIGCHLD] = event.Signal(signal.SIGCHLD, self._handleSigchld)
