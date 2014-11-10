# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Test cases for L{twisted.python.logger._io}.
"""

from __future__ import print_function

import sys

from twisted.trial import unittest

from .._levels import LogLevel
from .._logger import Logger
from .._observer import LogPublisher
from .._io import LoggingFile



class LoggingFileTests(unittest.TestCase):
    """
    Tests for L{LoggingFile}.
    """

    def setUp(self):
        """
        Create a logger for test L{LoggingFile} instances to use.
        """
        self.publisher = LogPublisher()
        self.logger = Logger(observer=self.publisher)


    def test_softspace(self):
        """
        L{LoggingFile.softspace} is 0.
        """
        self.assertEquals(LoggingFile.softspace, 0)


    def test_readOnlyAttributes(self):
        """
        Some L{LoggingFile} attributes are read-only.
        """
        f = LoggingFile(self.logger)

        self.assertRaises(AttributeError, setattr, f, "closed", True)
        self.assertRaises(AttributeError, setattr, f, "encoding", "utf-8")
        self.assertRaises(AttributeError, setattr, f, "mode", "r")
        self.assertRaises(AttributeError, setattr, f, "newlines", ["\n"])
        self.assertRaises(AttributeError, setattr, f, "name", "foo")


    def test_unsupportedMethods(self):
        """
        Some L{LoggingFile} methods are unsupported.
        """
        f = LoggingFile(self.logger)

        self.assertRaises(IOError, f.read)
        self.assertRaises(IOError, f.next)
        self.assertRaises(IOError, f.readline)
        self.assertRaises(IOError, f.readlines)
        self.assertRaises(IOError, f.xreadlines)
        self.assertRaises(IOError, f.seek)
        self.assertRaises(IOError, f.tell)
        self.assertRaises(IOError, f.truncate)


    def test_level(self):
        """
        Default level is L{LogLevel.info} if not set.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.level, LogLevel.info)

        f = LoggingFile(self.logger, level=LogLevel.error)
        self.assertEquals(f.level, LogLevel.error)


    def test_encoding(self):
        """
        Default encoding is C{sys.getdefaultencoding()} if not set.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.encoding, sys.getdefaultencoding())

        f = LoggingFile(self.logger, encoding="utf-8")
        self.assertEquals(f.encoding, "utf-8")


    def test_mode(self):
        """
        Reported mode is C{"w"}.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.mode, "w")


    def test_newlines(self):
        """
        The C{newlines} attribute is C{None}.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.newlines, None)


    def test_name(self):
        """
        The C{name} attribute is fixed.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(
            f.name,
            "<LoggingFile twisted.python.logger.test.test_io#info>"
        )


    def test_close(self):
        """
        L{LoggingFile.close} closes the file.
        """
        f = LoggingFile(self.logger)
        f.close()

        self.assertEquals(f.closed, True)
        self.assertRaises(ValueError, f.write, "Hello")


    def test_flush(self):
        """
        L{LoggingFile.flush} does nothing.
        """
        f = LoggingFile(self.logger)
        f.flush()


    def test_fileno(self):
        """
        L{LoggingFile.fileno} returns C{-1}.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.fileno(), -1)


    def test_isatty(self):
        """
        L{LoggingFile.isatty} returns C{False}.
        """
        f = LoggingFile(self.logger)
        self.assertEquals(f.isatty(), False)


    def test_write_buffering(self):
        """
        Writing buffers correctly.
        """
        f = self.observedFile()
        f.write("Hello")
        self.assertEquals(f.messages, [])
        f.write(", world!\n")
        self.assertEquals(f.messages, [u"Hello, world!"])
        f.write("It's nice to meet you.\n\nIndeed.")
        self.assertEquals(
            f.messages,
            [
                u"Hello, world!",
                u"It's nice to meet you.",
                u"",
            ]
        )


    def test_write_bytes_decoded(self):
        """
        Bytes are decoded to unicode.
        """
        f = self.observedFile(encoding="utf-8")
        f.write(b"Hello, Mr. S\xc3\xa1nchez\n")
        self.assertEquals(f.messages, [u"Hello, Mr. S\xe1nchez"])


    def test_write_unicode(self):
        """
        Unicode is unmodified.
        """
        f = self.observedFile(encoding="utf-8")
        f.write(u"Hello, Mr. S\xe1nchez\n")
        self.assertEquals(f.messages, [u"Hello, Mr. S\xe1nchez"])


    def test_write_level(self):
        """
        Log level is emitted properly.
        """
        f = self.observedFile()
        f.write("Hello\n")
        self.assertEquals(len(f.events), 1)
        self.assertEquals(f.events[0]["log_level"], LogLevel.info)

        f = self.observedFile(level=LogLevel.error)
        f.write("Hello\n")
        self.assertEquals(len(f.events), 1)
        self.assertEquals(f.events[0]["log_level"], LogLevel.error)


    def test_write_format(self):
        """
        Log format is C{u"{message}"}.
        """
        f = self.observedFile()
        f.write("Hello\n")
        self.assertEquals(len(f.events), 1)
        self.assertEquals(f.events[0]["log_format"], u"{message}")


    def test_writelines_buffering(self):
        """
        C{writelines} does not add newlines.
        """
        # Note this is different behavior than t.p.log.StdioOnnaStick.
        f = self.observedFile()
        f.writelines(("Hello", ", ", ""))
        self.assertEquals(f.messages, [])
        f.writelines(("world!\n",))
        self.assertEquals(f.messages, [u"Hello, world!"])
        f.writelines(("It's nice to meet you.\n\n", "Indeed."))
        self.assertEquals(
            f.messages,
            [
                u"Hello, world!",
                u"It's nice to meet you.",
                u"",
            ]
        )


    def test_print(self):
        """
        L{LoggingFile} can replace L{sys.stdout}.
        """
        oldStdout = sys.stdout
        try:
            f = self.observedFile()
            sys.stdout = f

            print("Hello,", end=" ")
            print("world.")

            self.assertEquals(f.messages, [u"Hello, world."])
        finally:
            sys.stdout = oldStdout


    def observedFile(self, **kwargs):
        """
        Construct a L{LoggingFile} with a built-in observer.

        @param kwargs: keyword arguments for the L{LoggingFile}.
        @type kwargs: L{dict}

        @return: a L{LoggingFile} with an observer that appends received
            events into the file's C{events} attribute (a L{list}) and
            event messages into the file's C{messages} attribute (a L{list}).
        @rtype: L{LoggingFile}
        """
        def observer(event):
            f.events.append(event)
            if "message" in event:
                f.messages.append(event["message"])

        log = Logger(observer=observer)

        f = LoggingFile(logger=log, **kwargs)
        f.events = []
        f.messages = []

        return f
