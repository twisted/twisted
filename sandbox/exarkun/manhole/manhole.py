
import code, sys

import insults, recvline

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
    def __init__(self, handler, locals=None, filename="<console>"):
        code.InteractiveInterpreter.__init__(self, locals)
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
        orighook, sys.displayhook = sys.displayhook, lambda s: self.write(repr(s))
        try:
            origout, sys.stdout = sys.stdout, FileWrapper(self.handler)
            try:
                code.InteractiveInterpreter.runcode(self, *a, **kw)
            finally:
                sys.stdout = origout
        finally:
            sys.displayhook = orighook

    def write(self, data):
        self.handler.addOutput(data)

class Manhole(recvline.HistoricRecvLineHandler):
    def __init__(self, proto):
        recvline.HistoricRecvLineHandler.__init__(self, proto)
        self.interpreter = ManholeInterpreter(self)

    def addOutput(self, bytes):
        self.proto.write(bytes.replace('\n', '\r\n'))

    def lineReceived(self, line):
        more = self.interpreter.push(line)
        self.pn = bool(more)
        if not self.proto.lastWrite.endswith('\r\n') and not self.proto.lastWrite.endswith('\x1bE'):
            self.proto.write('\r\n')
        self.proto.write(self.ps[self.pn])

from twisted.application import service
application = service.Application("Interactive Python Interpreter")

from demolib import makeService
makeService({'handler': Manhole,
             'telnet': 6023,
             'ssh': 6022}).setServiceParent(application)
