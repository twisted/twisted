"""
Tests for L{twisted.threads._threadworker}.
"""

from twisted.trial.unittest import SynchronousTestCase

from .. import ThreadWorker

class FakeThread(object):
    """
    

    @ivar target: 
    @type target: 
    """

    def __init__(self, target):
        """
        

        @param target: 
        @type target: 
        """
        self.target = target
        self.started = False


    def start(self):
        """
        
        """
        self.started = True


class FakeQueue(object):
    """
    
    """

    def __init__(self):
        """
        
        """
        self.items = []


    def put(self, item):
        """
        
        """
        self.items.append(item)


    def get(self):
        """
        
        """
        return self.items.pop(0)



class ThreadWorkerTests(SynchronousTestCase):
    """
    Tests for L{ThreadWorker}
    """

    def test_startsThreadAndPerformsWork(self):
        """
        L{ThreadWorker} calls its C{createThread} callable to create a thread,
        its C{createQueue} callable to create a queue, and then the thread's
        target pulls work from that queue.
        """
        fakeThreads = []
        fakeQueue = FakeQueue()
        worker = ThreadWorker(lambda *a, **kw:
                              fakeThreads.append(FakeThread(*a, **kw)) or
                              fakeThreads[-1],
                              lambda: fakeQueue)
        self.assertEqual(len(fakeThreads), 1)
        self.assertEqual(fakeThreads[0].started, True)
        def doIt():
            doIt.done = True
        doIt.done = False
        worker.do(doIt)
        self.assertEqual(doIt.done, False)
        self.assertRaises(IndexError, fakeThreads[0].target)
        self.assertEqual(doIt.done, True)
