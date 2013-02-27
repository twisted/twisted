#!/usr/bin/env python

"""
Benchmark to test the performance of
basic.(LineOnlyReceiver|LineReceiver|IntNStringReceiver) when receiving
very fragmented packets.

This benchmark was created to verify that the patch reducing the time
complexity of these protocols from O(n^2) to O(n) worked correctly, and
to make sure that the non-pathological cases didn't result in any
performance degradation.

This benchmark makes each tested protocol receive N messages, each split
into X packets of M bytes, with X varying.

Run with args: <N> <M> <min(X)> <max(X)> <step>.

The output is: <X> <runtime(LineOnlyReceiver)> <runtime(LineReceiver)> <runtime(IntNStringReceiver)>
"""

import time
import sys
import struct

from twisted.protocols import basic
from twisted.internet import protocol
from twisted.test.test_protocols import StringIOWithoutClosing

class NoopLineOnlyReceiver(basic.LineOnlyReceiver):
    MAX_LENGTH = 100000
    delimiter = '\n'

    def lineReceived(self, _):
        pass

class NoopLineReceiver(basic.LineReceiver):
    MAX_LENGTH = 100000
    delimiter = '\n'

    def lineReceived(self, _):
        pass

class NoopInt32Receiver(basic.Int32StringReceiver):
    MAX_LENGTH = 100000

    def stringReceived(self, _):
        pass

def run_lineonly_iteration(num_lines, pkts_per_line, packet_size):
    packet = 'a'*packet_size
    packet_with_delimiter = packet + '\n'

    t = StringIOWithoutClosing()
    a = NoopLineOnlyReceiver()
    a.makeConnection(protocol.FileWrapper(t))

    start = time.time()
    for _ in xrange(num_lines):
        for _ in xrange(pkts_per_line-1):
            a.dataReceived(packet)
        a.dataReceived(packet_with_delimiter)
    stop = time.time()
    return stop - start

def run_line_iteration(num_lines, pkts_per_line, packet_size):
    packet = 'a'*packet_size
    packet_with_delimiter = packet + '\n'

    t = StringIOWithoutClosing()
    a = NoopLineReceiver()
    a.makeConnection(protocol.FileWrapper(t))

    start = time.time()
    for _ in xrange(num_lines):
        for _ in xrange(pkts_per_line-1):
            a.dataReceived(packet)
        a.dataReceived(packet_with_delimiter)
    stop = time.time()
    return stop - start

def run_int32_iteration(num_lines, pkts_per_msg, packet_size):
    packet = 'a'*packet_size
    packet_with_prefix = struct.pack('!I', pkts_per_msg*packet_size) + packet

    t = StringIOWithoutClosing()
    a = NoopInt32Receiver()
    a.makeConnection(protocol.FileWrapper(t))

    start = time.time()
    for _ in xrange(num_lines):
        for c in packet_with_prefix:
            a.dataReceived(c)
        for _ in xrange(pkts_per_msg-1):
            a.dataReceived(packet)
    stop = time.time()
    return stop - start

def run_over_range_of_num_pkts(num_lines, pkt_size, min, max, step):
    for num_pkts in xrange(min, max, step):
        t = run_lineonly_iteration(num_lines, num_pkts, pkt_size)
        t2 = run_line_iteration(num_lines, num_pkts, pkt_size)
        t3 = run_int32_iteration(num_lines, num_pkts, pkt_size)
        print "%d %f %f %f" % (num_pkts, t, t2, t3)
        sys.stdout.flush()

def main():
    run_over_range_of_num_pkts(*[int(x) for x in sys.argv[1:]])

if __name__ == '__main__':
    main()
