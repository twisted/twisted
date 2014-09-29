
"""
Since we can't safely use python stdlib L{Queue} or L{RLock}, (see
U{http://bugs.python.org/issue13697}) implement our own in terms of pipes,
lists, and the GIL.

I can almost hear you asking, "why aren't you using a deque, isn't that the
more natural structure for this"?  I'm sticking with lists for the time being
because the impetus for this whole package is basically that everything in the
world is broken, so I want to stick with the absolute minimal data structures
possible to implement the functionality, then stress test the heck out of any
optimizations.  Given that lists are a syntactic feature of the language and
deques are an import away, it seems like they'd have a lot more test coverage
out in the wild.
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
