
"""
Since we can't safely use python stdlib L{Queue} or L{RLock}, (see
U{http://bugs.python.org/issue13697}) implement our own in terms of pipes and
the GIL.
"""

import os

class PipeQueue(object):
    """
    A FIFO queue implemented with a pipe and a list.
    """

    def __init__(self):
        """
        Create a queue.
        """
        self._r, self._w = os.pipe()
        self._data = []


    def put(self, item):
        """
        Put an item into the queue.
        """
        self._data.append(item)
        os.write(self._w, b'0')


    def get(self):
        """
        Get an item that was put into the queue with C{put}.
        """
        os.read(self._r, 1)
        self._data.pop(0)
