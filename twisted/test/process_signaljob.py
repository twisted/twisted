from twisted.internet import reactor, protocol
import sys, signal, time

signal.signal(signal.SIGINT, signal.SIG_DFL)

if sys.argv[1] == "parent":
    class WaitProcessProtocol(protocol.ProcessProtocol):
        def outReceived(self, data):
            print 'ok, signal us'

    p = WaitProcessProtocol()
    exe = sys.executable
    reactor.spawnProcess(p, exe, [exe, "-u", __file__, "child"], env=None)

    reactor.run(installSignalHandlers=False)
else:
    print 'ok, signal us'
    # Ideally, I would wait on sys.stdin.read() here. But when the parent
    # terminates, it's closed so the child is terminated too.
    time.sleep(120)
    sys.exit(1)
