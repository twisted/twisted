"""Non-twisted throughput client."""

import socket
import sys
import time

TIMES = 50000
S = "0123456789" * 1024
sent = len(S) * TIMES


def main():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((sys.argv[1], int(sys.argv[2])))
    start = time.time()
    i = 0
    while i < TIMES:
        i += 1
        s.sendall(S)
    passed = time.time() - start
    print("Throughput: %s kbytes/sec" % ((sent / passed) / 1024))
    s.close()


if __name__ == "__main__":
    main()
