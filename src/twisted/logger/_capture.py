# -*- test-case-name: twisted.logger.test.test_capture -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Context manager for capturing logs.
"""

from io import StringIO

from attr import Factory, attrib, attrs

from twisted.logger import globalLogPublisher, textFileLogObserver



@attrs(frozen=True, slots=True)
class LogCapture(object):
    """
    A context manager that captures log events.
    """

    publisher = attrib(default=globalLogPublisher)
    _events = attrib(factory=list, init=False)


    def __enter__(self):
        self.publisher.addObserver(self._events.append)
        return self


    def __exit__(self, type_, value_, tb_):
        self.publisher.removeObserver(self._events.append)


    @property
    def events(self):
        """
        @return: the captured events
        @rtype: L{list}
        """
        return self._events.copy()


    def asText(self):
        """
        Get captured events as a string as produced by L{textFileLogObserver}.

        @return: the captured log text
        @rtype: L{str}
        """
        io = StringIO()
        observer = textFileLogObserver(io)
        for event in self._events:
            observer(event)
        return io.getvalue()
