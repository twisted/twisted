
import code, sys

import insults, recvline

from twisted.internet import defer

class FileWrapper:
    softspace = 0

    def __init__(self, o):
        self.o = o

    def flush(self):
        pass

    def write(self, data):
        self.o.addOutput(data)

    def writelines(self, lines):
        self.o.addOutput(''.join(lines))

class ManholeInterpreter(code.InteractiveInterpreter):
    numDeferreds = 0
    def __init__(self, handler, locals=None, filename="<console>"):
        code.InteractiveInterpreter.__init__(self, locals)
        self._pendingDeferreds = {}
        self.handler = handler
        self.filename = filename
        self.resetbuffer()

    def resetbuffer(self):
        """Reset the input buffer."""
        self.buffer = []

    def push(self, line):
        """Push a line to the interpreter.

        The line should not have a trailing newline; it may have
        internal newlines.  The line is appended to a buffer and the
        interpreter's runsource() method is called with the
        concatenated contents of the buffer as source.  If this
        indicates that the command was executed or invalid, the buffer
        is reset; otherwise, the command is incomplete, and the buffer
        is left as it was after the line was appended.  The return
        value is 1 if more input is required, 0 if the line was dealt
        with in some way (this is the same as runsource()).

        """
        self.buffer.append(line)
        source = "\n".join(self.buffer)
        more = self.runsource(source, self.filename)
        if not more:
            self.resetbuffer()
        return more

    def runcode(self, *a, **kw):
        orighook, sys.displayhook = sys.displayhook, self.displayhook
        try:
            origout, sys.stdout = sys.stdout, FileWrapper(self.handler)
            try:
                code.InteractiveInterpreter.runcode(self, *a, **kw)
            finally:
                sys.stdout = origout
        finally:
            sys.displayhook = orighook

    def displayhook(self, obj):
        if isinstance(obj, defer.Deferred):
            # XXX Ick, where is my "hasFired()" interface?
            if hasattr(obj, "result"):
                self.write(repr(obj))
            else:
                d = self._pendingDeferreds
                k = self.numDeferreds
                d[k] = obj
                self.numDeferreds += 1
                obj.addCallbacks(self._cbDisplayDeferred, self._ebDisplayDeferred,
                                 callbackArgs=(k,), errbackArgs=(k,))
                self.write("<Deferred #%d>" % (k,))
        else:
            self.write(repr(obj))

    def _cbDisplayDeferred(self, result, k):
        self.write("Deferred #%d called back: %r" % (k, result), True)
        del self._pendingDeferreds[k]
        return result

    def _ebDisplayDeferred(self, failure, k):
        self.write("Deferred #%d failed: %r" % (k, failure.getErrorMessage()), True)
        del self._pendingDeferreds[k]
        return failure

    def write(self, data, async=False):
        self.handler.addOutput(data, async)

class Manhole(recvline.HistoricRecvLine):

    def connectionMade(self):
        recvline.HistoricRecvLine.connectionMade(self)
        self.interpreter = ManholeInterpreter(self)
        self.keyHandlers['\x03'] = self.handle_INT
        self.keyHandlers['\x04'] = self.handle_QUIT
        self.keyHandlers['\x1c'] = self.handle_QUIT

    def handle_INT(self):
        self.transport.nextLine()
        self.transport.write("KeyboardInterrupt")
        self.transport.nextLine()
        self.transport.write(self.ps[self.pn])
        self.lineBuffer = []
        self.lineBufferIndex = 0

    def handle_QUIT(self):
        self.transport.loseConnection()

    def addOutput(self, bytes, async=False):
        if async:
            self.transport.eraseLine()
            self.transport.cursorBackward(len(self.lineBuffer) + len(self.ps[self.pn]))

        self.transport.write(bytes.replace('\n', '\r\n'))

        if async:
            if not self.transport.lastWrite.endswith('\r\n') and not self.transport.lastWrite.endswith('\x1bE'):
                self.transport.write('\r\n')
            self.transport.write(self.ps[self.pn] + ''.join(self.lineBuffer))

    def lineReceived(self, line):
        more = self.interpreter.push(line)
        self.pn = bool(more)
        if not self.transport.lastWrite.endswith('\r\n') and not self.transport.lastWrite.endswith('\x1bE'):
            self.transport.write('\r\n')
        self.transport.write(self.ps[self.pn])
