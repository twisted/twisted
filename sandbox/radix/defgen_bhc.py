
import sys
from twisted.python import log
log.startLogging(sys.stdout)


from bytecodehacks import macro

from twisted.internet import defer, reactor
from defgen import waitForDeferred, deferredGenerator

def someKindOfDeferred():
    d = defer.Deferred()
    reactor.callLater(1, d.callback, 'Hello!')
    return d

def wait((d)):
    x = waitForDeferred(d)
    yield x
    d = x.getResult()
macro.add_macro(wait)

def deferredUsingFunction():
    if 0:
        yield None
    d = someKindOfDeferred()
    wait(d)
    print d
    reactor.stop()
deferredUsingFunctionEx = macro.expand(deferredUsingFunction)
deferredUsingFunctionExEx = deferredGenerator(deferredUsingFunctionEx)

def main():
    deferredUsingFunctionExEx()
    reactor.run()
if __name__ == '__main__':
    main()
