# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""
ProcessMonitor: run processes, monitor progress, and restart when
they die.

The ProcessMonitor will not attempt to restart a process that appears
to die instantly -- with each "instant" death (less than 1 second, by
default), it will delay approximately twice as long before restarting
it. A successful run will reset the counter.

The primary interface is "addProcess" and "removeProcess". When the
service is active (that is, when the application it is attached to
is running), adding a process automatically starts it.

Each process has a name (a string). This string must uniquely identify
the process. In particular, attempting to add two processes with the
same name will result in a key error.

The arguments to addProcess are:
  - name -- a string, uniquely specifying the process
  - args -- a list of arguments. the first will be used to determine the
          executable
  - optionally, the uid and gid this process should be run as (by default,
    it does not change uid/gid before running processes).

Note that args are passed to the system call, not to the shell. If running
the shell is desired, the common idiom is to use
.addProcess("name", ['/bin/sh', '-c', shell_script])

removeProcess takes just the name argument. If the process is started, it
kills it, and will never restart it.

The "restartAll" method restarts all processes. This is useful for 3rd
parties management services to allow a user to restart servers because
of an outside circumstances change -- for example, a new version of a library
which is installed.

The following attributes on the monitor can be set to configure behaviour
  - threshold -- how long a process has to live before the death is considered
                 instant (default 1, measured in seconds)
  - killTime -- how long a process being killed has to get its affairs in
                order before it gets killed with an unmaskable signal
                (default 5, measured in seconds)
  - consistencyDelay -- time between consistency checks
                        (default 60, measured in seconds)
"""

import os, time
from signal import SIGTERM, SIGKILL
from twisted.python import log
from twisted.internet import protocol, reactor, process
from twisted.application import service
from twisted.protocols import basic

class DummyTransport:

    disconnecting = 0

transport = DummyTransport() 

class LineLogger(basic.LineReceiver):

    tag = None
    delimiter = '\n'

    def lineReceived(self, line):
        log.msg('[%s] %s' % (self.tag, line))

class LoggingProtocol(protocol.ProcessProtocol):

    service = None
    name = None
    empty = 1

    def connectionMade(self):
        self.output = LineLogger()
        self.output.tag = self.name
        self.output.makeConnection(transport)

    def outReceived(self, data):
        self.output.dataReceived(data)
        self.empty = data[-1] == '\n'

    errReceived = outReceived

    def processEnded(self, reason):
        if not self.empty:
            self.output.dataReceived('\n')
        self.service.connectionLost(self.name)


class ProcessMonitor(service.Service):

    threshold = 1
    active = 0
    killTime = 5
    consistency = None
    consistencyDelay = 60

    def __init__(self):
        self.processes = {}
        self.protocols = {}
        self.delay = {}
        self.timeStarted = {}
        self.murder = {}

    def __getstate__(self):
        dct = service.Service.__getstate__(self)
        for k in ('active', 'consistency'):
            if dct.has_key(k):
                del dct[k]
        dct['protocols'] = {}
        dct['delay'] = {}
        dct['timeStarted'] = {}
        dct['murder'] = {}
        return dct

    def _checkConsistency(self):
        for name, protocol in self.protocols.items():
            proc = protocol.transport
            try:
                proc.signalProcess(0)
            except (OSError, process.ProcessExitedAlready):
                log.msg("Lost process %r somehow, restarting." % name)
                del self.protocols[name]
                self.startProcess(name)
        self.consistency = reactor.callLater(self.consistencyDelay,
                                             self._checkConsistency)

    def addProcess(self, name, args, uid=None, gid=None):
        if self.processes.has_key(name):
            raise KeyError("remove %s first" % name)
        self.processes[name] = args, uid, gid
        if self.active:
            self.startProcess(name)

    def removeProcess(self, name):
        del self.processes[name]
        self.stopProcess(name)

    def startService(self):
        service.Service.startService(self)
        self.active = 1
        for name in self.processes.keys():
            reactor.callLater(0, self.startProcess, name)
        self.consistency = reactor.callLater(self.consistencyDelay,
                                             self._checkConsistency)

    def stopService(self):
        service.Service.stopService(self)
        self.active = 0
        for name in self.processes.keys():
            self.stopProcess(name)
        self.consistency.cancel()

    def connectionLost(self, name):
        if self.murder.has_key(name):
            self.murder[name].cancel()
            del self.murder[name]
        if self.protocols.has_key(name):
            del self.protocols[name]
        if time.time()-self.timeStarted[name]<self.threshold:
            delay = self.delay[name] = min(1+2*self.delay.get(name, 0), 3600)
        else:
            delay = self.delay[name] = 0
        if self.active and self.processes.has_key(name):
            reactor.callLater(delay, self.startProcess, name)

    def startProcess(self, name):
        if self.protocols.has_key(name):
            return
        p = self.protocols[name] = LoggingProtocol()
        p.service = self
        p.name = name
        args, uid, gid = self.processes[name]
        self.timeStarted[name] = time.time()
        reactor.spawnProcess(p, args[0], args, uid=uid, gid=gid)

    def _forceStopProcess(self, proc):
        try:
            proc.signalProcess(SIGKILL)
        except process.ProcessExitedAlready:
            pass

    def stopProcess(self, name):
        if not self.protocols.has_key(name):
            return
        proc = self.protocols[name].transport
        del self.protocols[name]
        try:
            proc.signalProcess(SIGTERM)
        except process.ProcessExitedAlready:
            pass
        else:
            self.murder[name] = reactor.callLater(self.killTime, self._forceStopProcess, proc)

    def restartAll(self):
        for name in self.processes.keys():
            self.stopProcess(name)

    def __repr__(self):
        l = []
        for name, proc in self.processes.items():
            uidgid = ''
            if proc[1] is not None:
                uidgid = str(proc[1])
            if proc[2] is not None:
                uidgid += ':'+str(proc[2])

            if uidgid:
                uidgid = '(' + uidgid + ')'
            l.append('%r%s: %r' % (name, uidgid, proc[0]))
        return ('<' + self.__class__.__name__ + ' '
                + ' '.join(l)
                + '>')

def main():
    mon = ProcessMonitor()
    mon.addProcess('foo', ['/bin/sh', '-c', 'sleep 2;echo hello'])
    mon.addProcess('qux', ['/bin/sh', '-c', 'sleep 2;printf pilim'])
    mon.addProcess('bar', ['/bin/sh', '-c', 'echo goodbye'])
    mon.addProcess('baz', ['/bin/sh', '-c',
                   'echo welcome;while :;do echo blah;sleep 5;done'])
    reactor.callLater(30, lambda mon=mon:
                          os.kill(mon.protocols['baz'].transport.pid, SIGTERM))
    reactor.callLater(60, mon.restartAll)
    mon.startService()
    reactor.addSystemEventTrigger('before', 'shutdown', mon.stopService)
    reactor.run()

if __name__ == '__main__':
   main()
