#!/usr/bin/python2.3

import re, os, sys

from twisted.internet import protocol, reactor, defer
from twisted.python.procutils import spawnProcess


class ProcProto(protocol.ProcessProtocol):
    reacter = debug = None

    def outReceived(self, data):
        """Some data was received from stdout."""
        if self.debug:
            print "OUT: %r" % (data,)
        self.reacter(data)

    def errReceived(self, data):
        """Some data was received from stderr."""
        if self.debug:
            print "ERR: %r" % (data,)

    def inConnectionLost(self):
        """This will be called when stdin is closed."""

    def outConnectionLost(self):
        """This will be called when stdout is closed."""

    def errConnectionLost(self):
        """This will be called when stderr is closed."""

    def processEnded(self, reason):
        """This will be called when the subprocess is finished.

        @type reason: L{twisted.python.failure.Failure}
        """


class Expect(object):
    child = _step = None
    
    def __init__(self):
        self.seq = []

    def spawnChild(self, executable, args=(), env={}, path=None, uid=None,
                 gid=None, usePTY=1, packages=()):
        self.child = ProcProto()

        self.child.reacter = self._react
#        self.child.debug = True
        spawnProcess(self.child, executable, args, env, path, uid, gid, usePTY, packages)

    def expect(self, pattern, timeout=None):
        self.seq.append(('expect', re.compile(pattern), timeout))

    def expectAndCall(self, pattern, f, *a, **kw):
        self.seq.append(('expectAndCall', re.compile(pattern), f, a, kw))

    def send(self, data=''):
        self.seq.append(('send', data))

    def sendline(self, data=''):
        self.seq.append(('send', data + os.linesep))

    def getStep(self):
        print "getStep: %r" % (self._step,)
        return self._step

    def setStep(self, val):
        print "setStep: %r" % (val,)
        self._step = val

    step = property(getStep, setStep)

    def _react(self, data):
        if not self.seq:
            return
        
        if self.step is None:
            self.step = self.seq.pop(0)

        s = self.step
           
        if s[0] == 'expect' or s[0] == 'expectAndCall':
            if s[1].search(data): # we match, so run the next step
                if s[0] == 'expectAndCall':
                    print "expectAndCall reached"
                    self.step = None
                    s[2](s[3], s[4])
                if self.seq:
                    self.step = s = self.seq.pop(0)
                if s[0] == 'expect':
                    return
                elif s[0] == 'send':
                    self.child.transport.write(s[1])
                    self.step = None
                    return
                else:
                    raise RuntimeError, "something un-Expected happened"
        else:
            if s[0] != 'send':
                raise RuntimeError, 'this is weird'
            self.child.transport.write(s[1])
            self.step = None

def done():
    print "done called"
    reactor.stop()

def runTest():
    e = Expect()
    e.expect(r'you need to have a C compiler installed')
    e.sendline('yes')
    e.expect(r'kernel?')
    e.sendline()
    e.expect(r"Would you like to skip networking setup and keep your old settings as they are")
    e.sendline("yes")
    e.expect(r"virtual machines to access the host's")
    e.sendline("no")
    e.expectAndCall("You can now run VMware", done)
    e.spawnChild('/usr/local/bin/vmware-config.pl', args=('vmware-config.pl',), env=os.environ)


if __name__ == '__main__':
    runTest()
    reactor.run()
