# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
# 

"""Utility methods."""

from twisted.internet import protocol, reactor, defer
import cStringIO


def _callProtocolWithDeferred(protocol, executable, args=(), env={}, path='.'):
    d = defer.Deferred() 
    p = protocol(d)
    reactor.spawnProcess(p, executable, (executable,)+args, env, path)
    return d


class _BackRelay(protocol.ProcessProtocol):

    def __init__(self, deferred):
        self.deferred = deferred
        self.s = cStringIO.StringIO()

    def errReceived(self, text):
        self.deferred.errback(failure.Failure(IOError("got stderr")))
        self.deferred = None
        self.transport.loseConnection()

    def outReceived(self, text):
        self.s.write(text)

    def processEnded(self, reason):
        if self.deferred is not None:
            self.deferred.callback(self.s.getvalue())


def getProcessOutput(executable, args=(), env={}, path='.', reactor=reactor):
    """Spawn a process and return its output as a deferred returning a string.

    @param executable: The file name to run and get the output of - the
                       full path should be used.

    @param args: the command line arguments to pass to the process; a
                 sequence of strings. The first string should be the
                 executable's name.

    @param env: the environment variables to pass to the processs; a
                dictionary of strings.

    @param path: the path to run the subprocess in - defaults to the
                 current directory.

    @param reactor: the reactor to use - defaults to the default reactor
    """
    return _callProtocolWithDeferred(_BackRelay, executable, args, env, path,
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
