"""Test pausing on proceses. Be sure to run in unbuffered mode."""
import time, sys, threading


class CheckIfPaused(threading.Thread):

    def run(self):
        self.time = None
        while 1:
            last = self.time
            time.sleep(0.1)
            
sys.stdin.read(1)

# at this point we should be paused for a second after we write enough to block
start = time.time()
s = "aaaaaaaaaa" * 1600
for i in range(100):
    start = time.time()
    sys.stdout.write(s)
    if time.time() - start > 0.1:
        # we presumably were blocked
        break

# unpaused
sys.stdout.write("%.3f" % (time.time() - start))
