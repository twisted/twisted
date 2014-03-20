
"""
Benchmarks for L{twisted.internet.task}.
"""

from timer import timeit

from twisted.internet import task

def test_performance():
    """
    L{LoopingCall} should not take long to skip a lot of iterations.
    """
    clock = task.Clock()
    call = task.LoopingCall(lambda: None)
    call.clock = clock

    call.start(0.1)
    clock.advance(1000000)


def main():
    print "LoopingCall large advance takes", timeit(test_performance, iter=1)

if __name__ == '__main__':
    main()
