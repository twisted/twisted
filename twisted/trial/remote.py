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

"""Remote reporting for Trial.

For reporting test results in a seperate process.
"""

from __future__ import nested_scopes

from twisted.python.compat import *

import unittest

from twisted.internet import protocol
from twisted.python import components, failure
from twisted.spread import banana, jelly

import os

class OneWayBanana(banana.Banana):
    # There can be no negotiation on a one-way stream, so only offer one
    # dialect.
    knownDialects = ["none"]
    isClient = 0

    def connectionMade(self):
        banana.Banana.connectionMade(self)
        # We won't be getting the negotiation response, so select the dialect
        # now.
        self._selectDialect("none")

class JellyReporter(unittest.Reporter):
    """I report results as a Banana-encoded Jelly stream.

    This reporting format is machine-readable.  It might make more sense
    to proxy to a pb.Referenceable Reporter, but then it would need a
    two-way connection and a reactor running to manage the protocol I'm
    not sure if we want to do that.

    Decode this stream with L{DecodeReport}.
    """

    doSendTimes = True
    
    def __init__(self, stream=None):
        self.stream = stream
        self.banana = OneWayBanana(isClient=0)
        if stream is not None:
            self.makeConnection(stream)
        unittest.Reporter.__init__(self)

    def reportImportError(self, name, exc):
        f = failure.Failure(exc)
        self.jellyMethodCall("reportImportError", name, f)
        unittest.Reporter.reportImportError(self, name, exc)

    def jellyMethodCall(self, methodName, *args):
        if self.doSendTimes:
            sexp = jelly.jelly((methodName, args, os.times()))
        else:
            sexp = jelly.jelly((methodName, args))            
        self.banana.sendEncoded(sexp)


    ## These should be delegated to my Protocol component.

    def makeConnection(self, transport):
        self.banana.makeConnection(transport)


    ## In case I accidently got hooked up to something which is feeding
    ## me data (e.g. the loopback tests).        
    
    def dataReceived(self, data):
        if not data:
            pass
        elif (not self._gotNegotiation) and (data == '\x04\x82none'):
            self._gotNegotiation = data
        else:
            raise ValueError("I should not be getting this data", data)

    _gotNegotiation = None

    def connectionLost(self, reason):
        pass

## Fun with dynamic method creation.  For each of Reporter's methods, make
## a JellyReporter version that sends the message to the jelly stream.
# (Should this have used t.p.hook?  I'm not convinced that would be
# any cleaner.)
import new
for methodName in ("start", "stop",
                   "reportStart", "reportSkip",
                   "reportFailure", "reportError", "reportSuccess"):
    reporterMethod = getattr(JellyReporter, methodName)
    if methodName in ('reportSkip','reportFailure','reportError'):
        # These methods have a exc_info -> Failure transformation.
        def replacement(self, testClass, method, exc_info):
            typ, val, tb = exc_info
            f = failure.Failure(val, typ, tb)
            self.jellyMethodCall(methodName, testClass, method, f)
            return reporterMethod(self, testClass, method, exc_info)
    else:
        def replacement(self, *args):
            self.jellyMethodCall(methodName, *args)
            return reporterMethod(self, *args)
    replacement = new.function(replacement.func_code,
                               {'failure': failure,
                                'reporterMethod': reporterMethod,
                                'methodName': methodName},
                               methodName)
    setattr(JellyReporter, methodName, replacement)
del reporterMethod
del methodName

class NullTransport:
    """Transport to /dev/null."""
    def write(self, *bytes):
        return

class IRemoteReporter(components.Interface):
    """I am reporting results from a test suite running someplace else.

    The interface is mostly identical to unittest.Runner, the main difference
    being that where it uses exc_info tuples, I use L{failure.Failure}s.
    """

    # TODO: Figure out where 'times' belongs in this interface.
    #    Is it a seperate method?  Is it an extra argument on every method?
    
    def remote_start(self, expectedTests, times=None):
        pass

    def remote_reportImportError(self, name, aFailure, times=None):
        pass

    def remote_reportStart(self, testClass, method, times=None):
        pass

    def remote_reportSkip(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportFailure(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportError(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportSuccess(self, testClass, method, times=None):
        pass

    def remote_stop(self, times=None):
        pass

class DecodeReport(banana.Banana):
    def __init__(self, reporter):
        self.reporter = reporter

        banana.Banana.__init__(self)
        self.transport = NullTransport()
        self.connectionMade()

    def expressionReceived(self, lst):
        lst = jelly.unjelly(lst)
        methodName, args = lst[:2]
        if len(lst) > 2:
            times = lst[2]
        else:
            times = None
        if len(lst) > 3:
            raise ValueError("I did something wrong", len(lst))
        method = getattr(self.reporter, "remote_" + methodName, None)
        if method is not None:
            method(*(args + (times,)))

class TrialProcessProtocol(DecodeReport, protocol.ProcessProtocol):
    def outReceived(self, data):
        return self.dataReceived(data)

    def errReceived(self, data):
        self.log(data)

class DemoRemoteReporter:
    __implements__ = (IRemoteReporter,)
    
    def remote_start(self, expectedTests, times=None):
        self.startTimes = times
        self.printTimeStamped(times, "start")

    def remote_reportImportError(self, name, aFailure, times=None):
        pass

    def remote_reportStart(self, testClass, method, times=None):
        self.printTimeStamped(times, "startTest", method)

    def remote_reportSkip(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportFailure(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportError(self, testClass, method, aFailure, times=None):
        pass

    def remote_reportSuccess(self, testClass, method, times=None):
        pass

    def remote_stop(self, times=None):
        self.endTimes = times
        self.printTimeStamped(times, "Done!")
        usert, syst, wallt = (self.endTimes[0] - self.startTimes[0],
                              self.endTimes[1] - self.startTimes[1],
                              self.endTimes[-1] - self.startTimes[-1])
        print "CPU time: %.2f  Wall clock time: %.2f" % (usert+syst,
                                                         wallt)

    def printTimeStamped(self, times, *args):
        print ("%.2f %.2f %.2f %.2f %.2f " % times), " ".join(map(str, args))


from twisted.internet import app
class _Demo(app.ApplicationService):
    """Demonstrate trial.remote by spawning trial in a subprocess
    and displaying results.  Wrapped in an ApplicationService so I can
    use twistd --debug on it.
    """
    
    def startService(self):
        from twisted.internet import reactor
        from twisted.python import log
        from twisted.trial import remote
        reporter = remote.DemoRemoteReporter()
        proto = remote.TrialProcessProtocol(reporter)
        def processEnded(reason):
            log.err(reason)
            reactor.callLater(0, reactor.stop)
            
        proto.processEnded = processEnded
        targs = ('--jelly', '-m', 'twisted.test.test_trial')
        log.msg("Running `bin/trial %s`" % (" ".join(targs),))
        reactor.spawnProcess(proto, "bin/trial", ('trial',) + targs)

def demo():
    """Make a .tap which will demonstrate trial.remote."""
    from twisted.trial import remote
    myApp = app.Application("tdemo")
    remote._Demo("trialDemo", myApp)
    myApp.save()
    print "demo saved to tdemo.tap"


# Local Variables:
# test-case-name: "twisted.test.test_trial"
# End:
