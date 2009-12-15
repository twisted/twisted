import time, sys, signal

signal.signal(signal.SIGHUP, signal.SIG_DFL)
if sys.argv[1] == "parent":
    from popen2 import Popen4
    import os
    try:
        os.setsid()
    except OSError:
        # If it's a PTY process, the call has already been made
        pass
    process = Popen4("%s -u %s child" % (sys.executable, __file__))
    stdout = process.fromchild.readline()
    def handle(*args):
        # Wait for child to terminate
        process.wait()
        # Put back SIG_DFL
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        # Re-signal
        os.kill(os.getpid(), signal.SIGINT)
    signal.signal(signal.SIGINT, handle)
    print 'ok, signal us'
    sys.stdin.read()
    sys.exit(1)
else:
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    print 'ok, signal us'
    sys.stdin.read()
    sys.exit(1)
