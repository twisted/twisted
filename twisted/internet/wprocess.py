"""A process implementation that uses Trent Mick's tmprocess.py.
"""
from twisted.python import threadable, failure, log
threadable.init(1)
from twisted.internet import error, threads
import os
from twisted.python import process as tmprocess

class ReactorBuffer(tmprocess.IOBuffer):
    """
    rb = ReactorBuffer(reactor, outLost_cb, outRecv_cb) # create stdout buf
    rb = ReactorBuffer(reactor, errLost_cb, errRecv_cb) # create stderr buf
    rb = ReactorBuffer(reactor, inLost_cb, None) # create stdin buf
    """
    def __init__(self, reactor, lost, receiver=None):
        assert callable(lost)
        self.reactor = reactor
        self.receiver = receiver 
        self.lost = lost
        tmprocess.IOBuffer.__init__(self)
        self.closing = 0
        self.started = 0 # if Process.__init__ raises an exception, this keeps
                         # self.lost from getting called spuriously
    def _doWrite(self, s):
        if callable(self.receiver): 
            self.reactor.callFromThread(self.receiver, s)
        tmprocess.IOBuffer._doWrite(self, s)
    def _doClose(self):
        if not self.started:
            return
        if not self.closing:
            self.closing = 1
            self.reactor.callFromThread(self.lost)
            tmprocess.IOBuffer._doClose(self)

class Process:
    def __init__(self, reactor, protocol, command, args, environment, path):
        self.protocol = protocol
        self.waiting = None
        self.stdin = ReactorBuffer(reactor, self.inConnectionLost)
        self.stderr = ReactorBuffer(reactor, self.errConnectionLost,
                                    protocol.errReceived)
        self.stdout = ReactorBuffer(reactor, self.outConnectionLost,
                                    protocol.outReceived)
        self.process = tmprocess.ProcessProxy([command] + args, mode='b', 
                                              cwd=path, env=environment,
                                              stdin=self.stdin,
                                              stderr=self.stderr,
                                              stdout=self.stdout,
                                              )
        self.stderr.started = self.stdout.started = self.stdin.started = 1
        protocol.makeConnection(self)

    def killProcess(self, gracePeriod=1):
        """A poor-man's replacement for signalProcess.  This uses WM_CLOSE.
        @arg gracePeriod: int number of seconds process is allowed before being
                          forcibly killed 
        """
        # OOG, break abstraction.
        if not self.process._closed:
            self._processEnding = threads.deferToThread(self.process.kill, 
                                                        gracePeriod)
            (self._processEnding.addCallback(lambda _: self.maybeConnectionLost)
                                .addErrback(log.err))


    def write(self, data):
        self.stdin.write(data)
        # TODO - handle errors :P

    def loseConnection(self):
        self.closeStdout(); self.closeStderr(); self.closeStdin()

    def closeStdin(self):
        if self.stdin:
            self.stdin.close()
            self.stdin = None
            self.maybeConnectionLost()
    def closeStderr(self):
        if self.stderr:
            self.stderr.close()
            self.stderr = None
            self.maybeConnectionLost()
    def closeStdout(self):
        if self.stdout:
            self.stdout.close()
            self.stdout = None
            self.maybeConnectionLost()
    def maybeConnectionLost(self):
        """Called every time a connection to a fd is lost.
        If any of the three "out" fds remain open, do nothing.
        Otherwise, all are closed (so we can't do IO anyway..),
        therefore wait in a worker thread for the process to end.
        """
        if self.waiting is None:
            if not (self.stdin or self.stdout or self.stderr):
                self.waiting = threads.deferToThread(self.process.wait)
                (self.waiting.addCallback(self.connectionLost)
                             .addErrback(log.err))

    def outConnectionLost(self):
        self.closeStdout()
        self.protocol.outConnectionLost()
        self.maybeConnectionLost()
        
    def errConnectionLost(self):
        self.closeStderr()
        self.protocol.errConnectionLost()
        self.maybeConnectionLost()

    def inConnectionLost(self):
        self.closeStdin()
        self.protocol.inConnectionLost()
        self.maybeConnectionLost()

    def connectionLost(self, exitCode):
        if exitCode == 0:
            err = error.ProcessDone(exitCode)
        else:
            err = error.ProcessTerminated(exitCode)
        self.protocol.processEnded(failure.Failure(err))
