# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details..
# type: ignore

import os
import platform
import sys
import time
import tempfile
import os.path
from zope.interface import implementer
from twisted.internet import asyncfs
from twisted.internet.interfaces import (
    IPushProducer,
    IConsumer,
    FileAsyncFlags,
)
from twisted.python.filepath import FilePath
from twisted.trial import unittest
from twisted.internet.defer import DeferredList
from twisted.logger import globalLogBeginner, textFileLogObserver, Logger

log = Logger()
observers = [textFileLogObserver(sys.stdout)]
globalLogBeginner.beginLoggingTo(observers)

EIGHT_MEG_OF_BLAH = "blah" * (2 ** 21)  # needed to overwhelm RAM buffers


@implementer(IConsumer)
class FakeConsumer:
    def write(self, data):
        self.total_bytes += len(data)
        if self.total_bytes > 10000 and not self.done_flip:
            self.done_flip = True
            self.producer.pauseProducing()
            time.sleep(0.01)
            self.producer.resumeProducing()

    def __init__(self):
        self.done_flip = False
        self.total_bytes = 0

    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.streaming = streaming

    def unregisterProducer(self):
        self.producer = None


@implementer(IPushProducer)
class FakeProducer:
    def __init__(self):
        self.paused = False

    def pauseProducing(self):
        self.paused = True

    def resumeProducing(self):
        self.paused = False

    def fire(self, consumer):
        if not self.paused:
            consumer.write(EIGHT_MEG_OF_BLAH.encode("us-ascii"))


class TestFs(unittest.TestCase):
    def setUp(self):
        self.oldpath = os.getcwd()
        self.tpath = tempfile.mkdtemp()
        os.chdir(self.tpath)
        with open("one.txt", "w") as fd:
            fd.write("blah" * 3)
        with open("two.txt", "w") as fd:
            fd.write("blah")

    def tearDown(self):
        for i in os.listdir():
            # on Windows may need to wait for close()
            for _ in range(5):
                try:
                    os.unlink(i)
                    break
                except PermissionError:
                    time.sleep(1)
        os.chdir(self.oldpath)
        os.rmdir(self.tpath)

    def assertDir(self, dlist):
        dlist.sort()
        self.assertEqual(sorted(os.listdir()), dlist)

    def test_open(self):
        def cb_open(r):
            self.assertDir(["one.txt", "two.txt", "three.txt"])
            self.assertIsInstance(r[0][1], asyncfs.ThreadFileReader)
            self.assertIsInstance(r[1][1], asyncfs.ThreadFileWriter)
            os.close(r[0][1].fileno())
            os.close(r[1][1].fileno())

        d1 = asyncfs.openAsync(FilePath("one.txt"), FileAsyncFlags.READ)
        d2 = asyncfs.openAsync(FilePath("three.txt"), FileAsyncFlags.CREATE)
        d3 = DeferredList([d1, d2])
        d3.addCallback(cb_open)
        return d3

    def test_read(self):
        def cb_read2(res, fd):
            self.assertEqual(res, b"blah")
            os.close(fd.fileno())

        def cb_read1(fd):
            d2 = fd.read(4, 4)
            d2.addCallback(cb_read2, fd)
            return d2

        d1 = asyncfs.openAsync(FilePath("one.txt"), FileAsyncFlags.READ)
        d1.addCallback(cb_read1)
        return d1

    def test_write_close(self):
        def cb_write3(_):
            with open("three.txt") as fd:
                self.assertEqual(fd.read(), "lorem ipsum")

        def cb_write2(n, fd):
            self.assertEqual(n, 11)
            d3 = fd.close()
            d3.addCallback(cb_write3)
            return d3

        def cb_write1(fd):
            d2 = fd.write(0, b"lorem ipsum")
            d2.addCallback(cb_write2, fd)
            return d2

        d1 = asyncfs.openAsync(FilePath("three.txt"), FileAsyncFlags.CREATE)
        d1.addCallback(cb_write1)
        return d1

    def test_write_flush(self):
        def cb_write3(_, fd):
            with open("three.txt") as fd2:
                self.assertEqual(fd2.read(), "dolor sit")
            os.close(fd.fileno())

        def cb_write2(n, fd):
            self.assertEqual(n, 9)
            d3 = fd.flush()
            d3.addCallback(cb_write3, fd)
            return d3

        def cb_write1(fd):
            d2 = fd.write(0, b"dolor sit")
            d2.addCallback(cb_write2, fd)
            return d2

        d1 = asyncfs.openAsync(FilePath("three.txt"), FileAsyncFlags.CREATE)
        d1.addCallback(cb_write1)
        return d1

    def test_consumer(self):
        def cb_con2(_, fd, consumer):
            self.assertEqual(consumer.total_bytes, len(EIGHT_MEG_OF_BLAH))
            return fd.close()

        def cb_con1(fd):
            consumer = FakeConsumer()
            consumer.registerProducer(fd.producer(), True)
            d2 = fd.send(consumer)
            d2.addCallback(cb_con2, fd, consumer)
            return d2

        with open("bigfile.txt", "w") as fd:
            fd.write(EIGHT_MEG_OF_BLAH)
        d1 = asyncfs.openAsync(FilePath("bigfile.txt"), FileAsyncFlags.READ)
        d1.addCallback(cb_con1)
        return d1

    def test_producer(self):
        def cb_pro2(_):
            s = os.stat("bigfile.txt")
            self.assertEqual(s.st_size, len(EIGHT_MEG_OF_BLAH))

        def cb_pro1(fd):
            producer = FakeProducer()
            consumer = fd.receive()
            consumer.registerProducer(producer, True)
            producer.fire(consumer)
            d2 = fd.close()
            d2.addCallback(cb_pro2)
            return d2

        d1 = asyncfs.openAsync(FilePath("bigfile.txt"), FileAsyncFlags.CREATE)
        d1.addCallback(cb_pro1)
        return d1
