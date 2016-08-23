# -*- test-case-name: twisted.logger.test.test_assertionhelpers -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
General assertion helpers for testing log events.
"""

from contextlib import contextmanager

from twisted.logger import globalLogPublisher
from twisted.logger._legacy import _ensureCompatWithLegacyObservers



@contextmanager
def capturingLogEventsFrom(logger):
    """
    Context manager to accumulate log events emitted by a L{Logger}
    instance by passing list.append as an observer.

    @param logger: L{Logger} object that the event was emitted to.
    @type logger: L{Logger}
    """
    events = []
    logger.observer = events.append
    if logger.source is not None:
        logger.source._log = logger

    yield events



@contextmanager
def capturingLogEventsFromGlobalLogPublisher():
    """
    Context manager to accumulate log events emitted by a L{Logger}
    instance that is not directly accessible for testing, such as
    when L{twisted.logger._loggerFor} is used to create a L{Logger}
    on the fly. This is to avoid creating L{Logger} instance attributes in
    the Twisted codebase itself to avoid namespace conflicts for when end
    users subclass. In this case we don't assert log_logger in the event
    dict and ignore it and accumulate the events in a list by passing
    list.append as an observer to L{twisted.logger.globalLogPublisher}.
    In the event that the L{Logger} is an instance attribute,
    L{capturingLogEventsFrom} should be used in conjunction with
    L{assertGlobalLogEvent} and L{assertGlobalLogEvents} for optimum test
    coverage. Note that this is preferrably only for use in Twisted itself
    to facilitate default logging.
    """
    events = []
    globalLogPublisher.addObserver(events.append)

    yield events

    globalLogPublisher.removeObserver(events.append)



def assertGlobalLogEvent(testCase, event, log_level, log_namespace,
                         log_source=None, log_format=None, **kwargs):
    """
    Assertion helper for testing a single log event that has been
    emitted using L{twisted.logger._loggerFor}, in which case
    the L{Logger} that the event was emitted to may not be available
    for testing, hence no argument for log_logger. This helper should
    preferably be used in conjunction with the context manager
    L{capturingLogEventsFromGlobalLogPublisher} for optimum test
    coverage for events that can only be tested by passing an observer
    to a L{globalLogPublisher}.

    @param testCase: The L{TestCase} object that wants to test some
        log events using L{assertLogEvent}.
    @type testCase: L{TestCase}

    @param event: The emitted event, which is a L{dict}.
    @type event: L{dict}

    @param log_level: A L{LogLevel}.
    @type log_level: L{LogLevel}

    @param log_namespace: The namespace associated with the L{Logger}.
    @type log_namespace: L{str} (native string)

    @param log_source: The source object that emitted the event. This
        will be L{None} if the L{Logger} is not accessed as an
        attribute of an instance or class.
    @type log_source: L{object} or L{None}

    @param log_format: The format string provided for use by observers
        that wish to render the event as text. The format string uses
        new-style PEP 3101 formatting and is rendered using the log
        event (which is a L{dict}). This may be L{None}, if no format
        string was provided. The format string is optional, except when
        a failure is being logged using L{Logger.failure}, in which
        case a format string describing the failure must be provided.
    @type log_format: L{str} or L{None}

    @param kwargs: Additional key/value pairs that we expect to see
        in the event being tested. This L{dict} may contain key/value
        pairs needed to effectively render the format string.
    @type kwargs: L{dict}
    """
    expectedEvent = {
        'log_level': log_level, 'log_source': log_source,
        'log_format': log_format, 'log_namespace': log_namespace
    }
    expectedEvent.update(kwargs)
    expectedEvent.update(log_time=event['log_time'])
    if 'log_failure' in event:
        expectedEvent.update(log_failure=event['log_failure'])

    # Since we can't test log_logger, treat it like log_time
    expectedEvent.update(log_logger=event['log_logger'])

    # Compatibility with the old logging system, for more on this,
    # see twisted.logger._legacy.LegacyLogObserverWrapper and
    # twisted.logger._legacy.ensureCompatWithLegacyObservers
    expectedEvent = _ensureCompatWithLegacyObservers(expectedEvent)
    if event['log_format'] is not None:
        expectedEvent.update(log_legacy=event['log_legacy'])

    testCase.maxDiff = None

    testCase.assertEqual(event, expectedEvent)



def assertLogEvent(testCase, event, log_logger, log_level, log_namespace,
                   log_source=None, log_format=None, **kwargs):
    """
    Assertion helper for testing a single log event.

    @param testCase: The L{TestCase} object that wants to test some
        log events using L{assertLogEvent}.
    @type testCase: L{TestCase}

    @param event: The emitted event, which is a L{dict}.
    @type event: L{dict}

    @param log_logger: L{Logger} object that the event was emitted to.
    @type log_logger: L{Logger}

    @param log_level: A L{LogLevel}.
    @type log_level: L{LogLevel}

    @param log_namespace: The namespace associated with the L{Logger}.
    @type log_namespace: L{str} (native string)

    @param log_source: The source object that emitted the event. This
        will be L{None} if the L{Logger} is not accessed as an
        attribute of an instance or class.
    @type log_source: L{object} or L{None}

    @param log_format: The format string provided for use by observers
        that wish to render the event as text. The format string uses
        new-style PEP 3101 formatting and is rendered using the log
        event (which is a L{dict}). This may be L{None}, if no format
        string was provided. The format string is optional, except when
        a failure is being logged using L{Logger.failure}, in which
        case a format string describing the failure must be provided.
    @type log_format: L{str} or L{None}

    @param kwargs: Additional key/value pairs that we expect to see
        in the event being tested. This L{dict} may contain key/value
        pairs needed to effectively render the format string.
    @type kwargs: L{dict}
   """
    expectedEvent = {
        'log_logger': log_logger, 'log_level': log_level,
        'log_source': log_source, 'log_format': log_format,
        'log_namespace': log_namespace
    }
    expectedEvent.update(kwargs)
    expectedEvent.update(log_time=event['log_time'])
    if 'log_failure' in event:
        expectedEvent.update(log_failure=event['log_failure'])

    testCase.maxDiff = None

    testCase.assertEqual(event, expectedEvent)



def assertGlobalLogEvents(testCase, actualEvents, expectedEvents):
    """
    Assertion helper for testing multiple log events that have been
    emitted using L{twisted.logger._loggerFor}, in which case
    the L{Logger} that the event was emitted to may not be available
    for testing, therefore we do not test for it. This helper should
    preferably be used in conjunction with the context manager
    L{capturingLogEventsFromGlobalLogPublisher} for optimum test
    coverage for events that can only be tested by passing an observer
    to a L{globalLogPublisher}.

    @param testCase: The L{TestCase} object that wants to test some
        log events using L{assertLogEvents}.
    @type testCase: L{TestCase}

    @param actualEvents: A L{list} of L{dict} where each L{dict} is a
        logged event emitted to a L{Logger} that appends events
        to a L{list}.
    @type actualEvents: L{list} of L{dict}

    @param expectedEvents: A L{list} of L{dict} where each L{dict}
        consists of key/value pairs that the testing code expects
        to see in the C{actualEvents} being tested. The contents of
        a an example L{dict} in this L{list} would contain everything
        that you would pass to a valid call to L{assertGlobalLogEvent}.
    @type expectedEvents: L{list} of L{dict}
    """
    testCase.assertEqual(len(actualEvents), len(expectedEvents))

    for actualEvent, expectedEvent in zip(actualEvents, expectedEvents):
        assertGlobalLogEvent(testCase, actualEvent, **expectedEvent)



def assertLogEvents(testCase, actualEvents, expectedEvents):
    """
    Assertion helper for testing multiple log events.

    @param testCase: The L{TestCase} object that wants to test some
        log events using L{assertLogEvents}.
    @type testCase: L{TestCase}

    @param actualEvents: A L{list} of L{dict} where each L{dict} is a
        logged event emitted to a L{Logger} that appends events
        to a L{list}.
    @type actualEvents: L{list} of L{dict}

    @param expectedEvents: A L{list} of L{dict} where each L{dict}
        consists of key/value pairs that the testing code expects
        to see in the C{actualEvents} being tested.
    @type expectedEvents: L{list} of L{dict}
    """
    testCase.assertEqual(len(actualEvents), len(expectedEvents))

    for actualEvent, expectedEvent in zip(actualEvents, expectedEvents):
        assertLogEvent(testCase, actualEvent, **expectedEvent)



__all__ = ['assertLogEvent', 'assertLogEvents']
