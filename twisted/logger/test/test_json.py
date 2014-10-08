# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.logger._json}.
"""

from io import StringIO

from zope.interface.verify import verifyObject, BrokenMethodImplementation

from twisted.python.compat import unicode

from twisted.trial.unittest import TestCase

from twisted.python.failure import Failure

from .._observer import ILogObserver
from .._format import formatEvent
from .._levels import LogLevel
from .._flatten import extractField
from .._json import (
    eventAsJSON, eventFromJSON, jsonFileLogObserver, eventsFromJSONLogFile
)
from .._logger import Logger


def savedJSONInvariants(testCase, savedJSON):
    """
    Assert a few things about the result of L{eventAsJSON}, then return it.

    @param testCase: The L{TestCase} with which to perform the assertions.
    @type testCase: L{TestCase}

    @param savedJSON: The result of L{eventAsJSON}.
    @type savedJSON: L{unicode} (we hope)

    @return: C{savedJSON}
    @rtype: L{unicode}

    @raise AssertionError: If any of the preconditions fail.
    """
    testCase.assertIsInstance(savedJSON, unicode)
    testCase.assertEquals(savedJSON.count("\n"), 0)
    return savedJSON



class SaveLoadTests(TestCase):
    """
    Tests for loading and saving log events.
    """

    def savedEventJSON(self, event):
        """
        Serialize some an events, assert some things about it, and return the
        JSON.

        @param event: An event.
        @type event: L{dict}

        @return: JSON.
        """
        return savedJSONInvariants(self, eventAsJSON(event))


    def test_simpleSaveLoad(self):
        """
        Saving and loading an empty dictionary results in an empty dictionary.
        """
        self.assertEquals(eventFromJSON(self.savedEventJSON({})), {})


    def test_saveLoad(self):
        """
        Saving and loading a dictionary with some simple values in it results
        in those same simple values in the output; according to JSON's rules,
        though, all dictionary keys must be L{unicode} and any non-L{unicode}
        keys will be converted.
        """
        self.assertEquals(
            eventFromJSON(self.savedEventJSON({1: 2, u"3": u"4"})),
            {u"1": 2, u"3": u"4"}
        )


    def test_saveUnPersistable(self):
        """
        Saving and loading an object which cannot be represented in JSON will
        result in a placeholder.
        """
        self.assertEquals(
            eventFromJSON(self.savedEventJSON({u"1": 2, u"3": object()})),
            {u"1": 2, u"3": {u"unpersistable": True}}
        )


    def test_saveNonASCII(self):
        """
        Non-ASCII keys and values can be saved and loaded.
        """
        self.assertEquals(
            eventFromJSON(self.savedEventJSON(
                {u"\u1234": u"\u4321", u"3": object()}
            )),
            {u"\u1234": u"\u4321", u"3": {u"unpersistable": True}}
        )


    def test_saveBytes(self):
        """
        Any L{bytes} objects will be saved as if they are latin-1 so they can
        be faithfully re-loaded.
        """
        def asbytes(x):
            if bytes is str:
                return b"".join(map(chr, x))
            else:
                return bytes(x)

        inputEvent = {"hello": asbytes(range(255))}
        if bytes is not str:
            # On Python 3, bytes keys will be skipped by the JSON encoder. Not
            # much we can do about that.  Let's make sure that we don't get an
            # error, though.
            inputEvent.update({b"skipped": "okay"})
        self.assertEquals(
            eventFromJSON(self.savedEventJSON(inputEvent)),
            {u"hello": asbytes(range(255)).decode("charmap")}
        )


    def test_saveUnPersistableThenFormat(self):
        """
        Saving and loading an object which cannot be represented in JSON, but
        has a string representation which I{can} be saved as JSON, will result
        in the same string formatting; any extractable fields will retain their
        data types.
        """
        class Reprable(object):
            def __init__(self, value):
                self.value = value

            def __repr__(self):
                return("reprable")

        inputEvent = {
            "log_format": "{object} {object.value}",
            "object": Reprable(7)
        }
        outputEvent = eventFromJSON(self.savedEventJSON(inputEvent))
        self.assertEquals(formatEvent(outputEvent), "reprable 7")


    def test_extractingFieldsPostLoad(self):
        """
        L{extractField} can extract fields from an object that's been saved and
        loaded from JSON.
        """
        class Obj(object):
            def __init__(self):
                self.value = 345

        inputEvent = dict(log_format="{object.value}", object=Obj())
        loadedEvent = eventFromJSON(self.savedEventJSON(inputEvent))
        self.assertEquals(extractField("object.value", loadedEvent), 345)

        # The behavior of extractField is consistent between pre-persistence
        # and post-persistence events, although looking up the key directly
        # won't be:
        self.assertRaises(KeyError, extractField, "object", loadedEvent)
        self.assertRaises(KeyError, extractField, "object", inputEvent)


    def test_failureStructurePreserved(self):
        """
        Round-tripping a failure through L{eventAsJSON} preserves its class and
        structure.
        """
        events = []
        log = Logger(observer=events.append)
        try:
            1 / 0
        except ZeroDivisionError:
            f = Failure()
            log.failure("a message about failure", f)
        import sys
        if sys.exc_info()[0] is not None:
            # Make sure we don't get the same Failure by accident.
            sys.exc_clear()
        self.assertEquals(len(events), 1)
        loaded = eventFromJSON(self.savedEventJSON(events[0]))['log_failure']
        self.assertIsInstance(loaded, Failure)
        self.assertTrue(loaded.check(ZeroDivisionError))
        self.assertIsInstance(loaded.getTraceback(), str)


    def test_saveLoadLevel(self):
        """
        It's important that the C{log_level} key remain a
        L{twisted.python.constants.NamedConstant} object.
        """
        inputEvent = dict(log_level=LogLevel.warn)
        loadedEvent = eventFromJSON(self.savedEventJSON(inputEvent))
        self.assertIdentical(loadedEvent["log_level"], LogLevel.warn)


    def test_saveLoadUnknownLevel(self):
        """
        If a saved bit of JSON (let's say, from a future version of Twisted)
        were to persist a different log_level, it will resolve as None.
        """
        loadedEvent = eventFromJSON(
            '{"log_level": {"name": "other", '
            '"__class_uuid__": "02E59486-F24D-46AD-8224-3ACDF2A5732A"}}'
        )
        self.assertEquals(loadedEvent, dict(log_level=None))



class FileLogObserverTests(TestCase):
    """
    Tests for L{FileLogObserver}.
    """

    def test_interface(self):
        """
        L{FileLogObserver} is an L{ILogObserver}.
        """
        try:
            fileHandle = StringIO()
            observer = jsonFileLogObserver(fileHandle)
            try:
                verifyObject(ILogObserver, observer)
            except BrokenMethodImplementation as e:
                self.fail(e)

        finally:
            fileHandle.close()


    def test_observeWrites(self):
        """
        L{FileLogObserver} writes to the given file when it observes events.
        """
        try:
            fileHandle = StringIO()
            observer = jsonFileLogObserver(fileHandle)
            event = dict(x=1)
            observer(event)
            self.assertEquals(fileHandle.getvalue(), u'{"x": 1}\n')

        finally:
            fileHandle.close()


    def test_eventsFromJSONLogFile(self):
        """
        L{eventsFromJSONLogFile} reads events from a file.
        """
        try:
            fileHandle = StringIO(u'{"x": 1}\n')
            events = eventsFromJSONLogFile(fileHandle)

            nextEvent = next(events)
            self.assertEquals(nextEvent, {u"x": 1})

        finally:
            fileHandle.close()
