# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
# Author: Clark Evans  (cce@clarkevans.com)

"""
flow.pipe

This contains various filter stages which have exactly one input stage.  These
stages take a single input and modify its results, ie a rewrite stage.
"""

from base import *
from wrap import wrap
from twisted.python.failure import Failure

class Pipe(Stage):
    """ abstract stage which takes a single input stage """
    def __init__(self, source, *trap):
        Stage.__init__(self, *trap)
        self._source = wrap(source)

    def _yield(self):
        while not self.results \
          and not self.stop \
          and not self.failure:
            source = self._source
            instruction = source._yield()
            if instruction:
                return instruction
            if source.failure:
                self.failure = source.failure
                return
            results = source.results
            stop = source.stop
            if stop:
                self.stop = True
            source.results = []
            self.process(results, stop)

    def process(self, results):
        """ process implemented by the pipe

            Take a set of possibly empty results and sets the member 
            variables: results, stop, or failure appropriately
        """
        raise NotImplementedError

class Filter(Pipe):
    """
    flow equivalent to filter:  Filter(function, source, ... )

    Yield those elements from a source stage for which a function returns true.
    If the function is None, the identity function is assumed, that is, all
    items yielded that are false (zero or empty) are discarded.

    For example::

        def odd(val):
            if val % 2:
                return True

        def range():
            yield 1
            yield 2
            yield 3
            yield 4

        source = flow.Filter(odd,range)
        printFlow(source)
    """
    def __init__(self, func, source, *trap):
        Pipe.__init__(self, source, *trap)
        self._func = func

    def process(self, results, stop):
        self.results.extend(filter(self._func,results))

class LineBreak(Pipe):
    """ pipe stage which breaks its input into lines """
    def __init__(self, source, *trap, **kwargs):
        Pipe.__init__(self, source, *trap)
        self._delimiter = kwargs.get('delimiter','\r\n')
        self._maxlen    = int(kwargs.get('maxlength', 16384))+1
        self._trailer   = int(kwargs.get('trailer',False))
        self._buffer    = []     
        self._currlen   = 0

    def process(self, results, stop):
        for block in results:
            lines = str(block).split(self._delimiter)
            if len(lines) < 2:
                tail = lines[0]
            else:
                tail = lines.pop()
                if self._buffer:
                    self._buffer.append(lines.pop(0))
                    self.results.append("".join(self._buffer))
                    self._buffer = []
                self.results.extend(lines) 
                self._currlen = 0
            if tail:
                self._currlen += len(tail)
                self._buffer.append(tail)
        if stop and self._buffer:
            tail = "".join(self._buffer)
            if self._trailer:
                self.results.append(tail)
            else:
                raise RuntimeError, "trailing data remains: '%s'" % tail[:10]

