# -*- test-case-name: twisted.python.logger.test.test_legacy -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Integration with L{twisted.python.log}.
"""

from zope.interface import implementer

from ._levels import LogLevel
from ._format import formatEvent
from ._observer import ILogObserver
from ._stdlib import (
    toStdlibLogLevelMapping, fromStdlibLogLevelMapping, StringifiableFromEvent
)



@implementer(ILogObserver)
class LegacyLogObserverWrapper(object):
    """
    L{ILogObserver} that wraps an L{twisted.python.log.ILogObserver}.

    Received (new-style) events are modified prior to forwarding to
    the legacy observer to ensure compatibility with observers that
    expect legacy events.
    """

    def __init__(self, legacyObserver):
        """
        @param legacyObserver: an L{twisted.python.log.ILogObserver} to which
            this observer will forward events.
        """
        self.legacyObserver = legacyObserver


    def __repr__(self):
        return (
            "{self.__class__.__name__}({self.legacyObserver})"
            .format(self=self)
        )


    def __call__(self, event):
        """
        Forward events to the legacy observer after editing them to
        ensure compatibility.
        """

        # Twisted's logging supports indicating a python log level, so let's
        # provide the equivalent to our logging levels.
        level = event.get("log_level", None)
        if level in toStdlibLogLevelMapping:
            event["logLevel"] = toStdlibLogLevelMapping[level]

        # The "message" key is required by textFromEventDict()
        if "message" not in event:
            event["message"] = ()

        event["time"] = event["log_time"]

        event["system"] = event.get("log_system", "-")

        # Format new style -> old style
        if event.get("log_format", None) is not None and "format" not in event:
            # Create an object that implements __str__() in order to defer the
            # work of formatting until it's needed by a legacy log observer.
            event["format"] = "%(log_legacy)s"
            event["log_legacy"] = StringifiableFromEvent(event.copy())

        # From log.failure() -> isError blah blah
        if "log_failure" in event:
            event["failure"] = event["log_failure"]
            event["isError"] = 1
            event["why"] = formatEvent(event)
        elif "isError" not in event:
            event["isError"] = 0

        self.legacyObserver(event)



def publishToNewObserver(observer, eventDict, textFromEventDict):
    """
    Publish an old-style (L{twisted.python.log}) event to a new-style
    (L{twisted.python.logger}) observer.

    @note: It's possible that a new-style event was sent to a
        L{LegacyLogObserverWrapper}, and may now be getting sent back to a
        new-style observer.  In this case, it's already a new-style event,
        adapted to also look like an old-style event, and we don't need to
        tweak it again to be a new-style event, hence the checks for
        already-defined new-style keys.

    @param observer: A new-style observer to handle this event.
    @type observer: L{ILogObserver}

    @param eventDict: An L{old-style <twisted.python.log>}, log event.
    @type eventDict: L{dict}

    @param textFromEventDict: callable that can format an old-style event as a
        string.  Passed here rather than imported to avoid circular dependency.
    @type textFromEventDict: 1-arg L{callable} taking L{dict} returning L{str}

    @return: L{None}
    """

    if "log_time" not in eventDict:
        eventDict["log_time"] = eventDict["time"]

    if "log_format" not in eventDict:
        text = textFromEventDict(eventDict)
        if text is not None:
            eventDict["log_text"] = text
            eventDict["log_format"] = u"{log_text}"

    if "log_level" not in eventDict:
        if "logLevel" in eventDict:
            level = fromStdlibLogLevelMapping[eventDict["logLevel"]]
        elif eventDict["isError"]:
            level = LogLevel.critical
        else:
            level = LogLevel.info

        eventDict["log_level"] = level

    if "log_namespace" not in eventDict:
        eventDict["log_namespace"] = u"log_legacy"

    if "log_system" not in eventDict and "system" in eventDict:
        eventDict["log_system"] = eventDict["system"]

    observer(eventDict)
