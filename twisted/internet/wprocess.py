"""A process implementation that uses Trent Mick's tmprocess.py.
"""
from twisted.python import threadable, failure
threadable.init(1)
from twisted.internet import error, threads 
import os, sys
import tmprocess

class ReactorBuffer(tmprocess.IOBuffer):
    """
    rb = ReactorBuffer(outReceived_cb, outLost_cb) # create stdout buffer
    rb = ReactorBuffer(errReceived_cb, errLost_cb) # create stderr buffer
    rb = ReactorBuffer(None, inLost_cb) # create stdin buffer
    """
    def __init__(self, receiver=None, lost=None):
        self.receiver = receiver 
        self.lost = lost
        tmprocess.IOBuffer.__init__(self)
        self.closing = 0
    def _doWrite(self, s):
        self.receiver(s)
        tmprocess.IOBuffer._doWrite(self, s)
    def _doClose(self):
        if not self.closing:
            self.closing = 1
            self.lost()
            tmprocess.IOBuffer._doClose(self)
    def _doRead(self, n):
        # do i really need this? FIXME
        tmprocess.IOBuffer._doRead(self, n)

class Process:
    def __init__(self, reactor, protocol, command, args, environment, path):
        self.stdin = ReactorBuffer(None,
                                   self.inConnectionLost)
        self.stderr = ReactorBuffer(protocol.errReceived,
                                    self.errConnectionLost)
        self.stdout = ReactorBuffer(protocol.outReceived,
                                    self.outConnectionLost)
        self.process = tmprocess.ProcessProxy([command] + args, 
                                    mode='b', cwd=os.getcwd(), env=environment,
                                    stdin=self.stdin,
                                    stderr=self.stderr,
                                    stdout=self.stdout,
                                    )
        protocol.makeConnection(self)
        self.protocol = protocol
        self.waiting = None

#    TODO signalProcess(self, signalID):
#        if signalID in ("INT", "TERM", "KILL"):
#            ...

    def write(self, data):
        self.stdin.write(self, data)
        # TODO - handle errors :P

    def closeStdin(self):
        self.stdin.close()
        self.stdin = None
        self.maybeConnectionLost()
    def closeStderr(self):
        self.stderr.close()
        self.stderr = None
        self.maybeConnectionLost()
    def closeStdout(self):
        self.stdout.close()
        self.stdout = None
        self.maybeConnectionLost()
    def loseConnection(self):
        self.closeStdin()
        self.closeStdout()
        self.closeStderr()
    def maybeConnectionLost(self):
        """Called every time a connection to a fd is lost.
        If any of the three "out" fds remain open, do nothing.
        Otherwise, all are closed (so we can't do IO anyway..),
        therefore wait in a worker thread for the process to end.
        """
        if not self.waiting:
            if not (self.stdin or self.stdout or self.stderr):
                self.waiting = threads.deferToThread(self.process.wait)
                self.waiting.addBoth(self.connectionLost)

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
