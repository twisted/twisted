import time, sys, signal

signal.signal(signal.SIGINT, signal.SIG_DFL)
signal.signal(signal.SIGHUP, signal.SIG_DFL)
print 'ok, signal us'
time.sleep(5)
sys.exit(1)
