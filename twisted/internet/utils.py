# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

# 

"""Utility methods."""

from twisted.internet import protocol, reactor, defer
from twisted.python import failure

try:
    import cStringIO as StringIO
except ImportError:
    import StringIO

def _callProtocolWithDeferred(protocol, executable, args, env, path, reactor):
    d = defer.Deferred()
    p = protocol(d)
    reactor.spawnProcess(p, executable, (executable,)+tuple(args), env, path)
    return d


class _BackRelay(protocol.ProcessProtocol):

    def __init__(self, deferred, errortoo=0):
        self.deferred = deferred
        self.s = StringIO.StringIO()
        if errortoo:
            self.errReceived = self.errReceivedIsGood
        else:
            self.errReceived = self.errReceivedIsBad

    def errReceivedIsBad(self, text):
        if self.deferred is not None:
            self.deferred.errback(failure.Failure(IOError("got stderr: %r" % text)))
            self.deferred = None
            self.transport.loseConnection()

    def errReceivedIsGood(self, text):
        self.s.write(text)

    def outReceived(self, text):
        self.s.write(text)

    def processEnded(self, reason):
        if self.deferred is not None:
            self.deferred.callback(self.s.getvalue())


def getProcessOutput(executable, args=(), env={}, path='.', reactor=reactor,
                     errortoo=0):
    """Spawn a process and return its output as a deferred returning a string.

    @param executable: The file name to run and get the output of - the
                       full path should be used.

    @param args: the command line arguments to pass to the process; a
                 sequence of strings. The first string should *NOT* be the
                 executable's name.

    @param env: the environment variables to pass to the processs; a
                dictionary of strings.

    @param path: the path to run the subprocess in - defaults to the
                 current directory.

    @param reactor: the reactor to use - defaults to the default reactor
    @param errortoo: if 1, capture stderr too
    """
    return _callProtocolWithDeferred(lambda d: 
                                        _BackRelay(d, errortoo=errortoo),
                                     executable, args, env, path,
                                     reactor)


class _ValueGetter(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred

    def processEnded(self, reason):
        self.deferred.callback(reason.value.exitCode)


def getProcessValue(executable, args=(), env={}, path='.', reactor=reactor):
    """Spawn a process and return its exit code as a Deferred."""
    return _callProtocolWithDeferred(_ValueGetter, executable, args, env, path,
                                    reactor)


class _EverythingGetter(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred
        self.outBuf = StringIO.StringIO()
        self.errBuf = StringIO.StringIO()
        self.outReceived = self.outBuf.write
        self.errReceived = self.errBuf.write
    
    def processEnded(self, reason):
        out = self.outBuf.getvalue()
        err = self.errBuf.getvalue()
        e = reason.value
        code = e.exitCode
        if e.signal:
            self.deferred.errback((out, err, e.signal))
        else:
            self.deferred.callback((out, err, code))

def getProcessOutputAndValue(executable, args=(), env={}, path='.', 
                             reactor=reactor):
    """Spawn a process and returns a Deferred that will be called back with
    its output (from stdout and stderr) and it's exit code as (out, err, code)
    If a signal is raised, the Deferred will errback with the stdout and
    stderr up to that point, along with the signal, as (out, err, signalNum)
    """
    return _callProtocolWithDeferred(_EverythingGetter, executable, args, env, path,
                                    reactor)

