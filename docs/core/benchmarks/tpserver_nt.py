"""Non-twisted throughput server."""
from __future__ import print_function

import socket, signal, sys

def signalhandler(*args):
    print("alarm!")
    sys.stdout.flush()

signal.signal(signal.SIGALRM, signalhandler)

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(('', 8001))
s.listen(1)
while 1:
    c, (h, p) = s.accept()
    c.settimeout(30)
    signal.alarm(5)
    while 1:
        d = c.recv(16384)
        if not d:
            break
    c.close()
