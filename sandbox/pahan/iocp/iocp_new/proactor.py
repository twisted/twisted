from twisted.internet import defer, base, main
from twisted.internet.interfaces import IReactorCore, IReactorTime, IReactorTCP, IReactorUDP
from twisted.python import threadable, log

import tcp
from iocpcore import iocpcore

class Proactor(iocpcore, base.ReactorBase):
    __implements__ = base.ReactorBase.__implements__ + (IReactorTCP,)
    handles = None
    iocp = None

    def __init__(self):
        iocpcore.__init__(self)
        base.ReactorBase.__init__(self)
#        self.completables = {}

    def startRunning(self):
        threadable.registerAsIOThread()
        self.fireSystemEvent('startup')
        self.running = 1

    def run(self):
        self.startRunning()
        self.mainLoop()

    def mainLoop(self):
        while self.running:
            try:
                while self.running:
                    # Advance simulation time in delayed event
                    # processors.
                    self.runUntilCurrent()
                    t2 = self.timeout()
                    t = self.running and t2
                    self.doIteration(t)
            except:
                log.msg("Unexpected error in main loop.")
                log.deferr()
            else:
                log.msg('Main loop terminated.')

    def installWaker(self):
        pass

    def wakeUp(self):
        def ignore(ret, bytes):
            pass
        if not threadable.isInIOThread():
            self.issuePostQueuedCompletionStatus(ignore)
            
    def listenTCP(self, port, factory, backlog=5, interface=''):
        p = tcp.Port((interface, port), factory, backlog)
        p.startListening()
        return p

    def connectTCP(self, host, port, factory, timeout=30, bindAddress=None):
        c = tcp.Connector((host, port), factory, timeout, bindAddress)
        c.connect()
        return c

def install():
    p = Proactor()
    main.installReactor(p)

