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
from twisted.internet.interfaces import IPushProducer, IConsumer
from twisted.trial import unittest
from twisted.internet.defer import DeferredList
from twisted.logger import globalLogBeginner, textFileLogObserver, Logger

log = Logger()
observers = [textFileLogObserver(sys.stdout)]
globalLogBeginner.beginLoggingTo(observers)

ONE_MEG_OF_BLAH = "blah" * (2 ** 18)  # needed to overwhelm RAM buffers


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
            consumer.write(ONE_MEG_OF_BLAH.encode("us-ascii"))


class BaseTestFs:
    def setUp(self):
        self.oldpath = os.getcwd()
        self.tpath = tempfile.mkdtemp()
        os.chdir(self.tpath)
        with open("one.txt", "w") as fd:
            fd.write("blah" * 3)
        with open("two.txt", "w") as fd:
            fd.write("blah")
        self.fso = self.fso_class(root=self.tpath)

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
        self.fso.unregister()

    def assertDir(self, dlist):
        dlist.sort()
        self.assertEqual(sorted(os.listdir()), dlist)

    def test_open(self):
        def cb_open(r):
            self.assertDir(["one.txt", "two.txt", "three.txt"])
            os.close(r[0][1].fileno())
            os.close(r[1][1].fileno())

        d1 = self.fso.openFile("one.txt")
        d2 = self.fso.openFile("three.txt", os.O_CREAT | os.O_RDWR)
        d3 = DeferredList([d1, d2])
        d3.addCallback(cb_open)
        return d3

    def test_read(self):
        def cb_read2(res, fd):
            self.assertEqual(res, b"blah")
            os.close(fd.fileno())

        def cb_read1(fd):
            d2 = fd.readChunk(4, 4)
            d2.addCallback(cb_read2, fd)
            return d2

        d1 = self.fso.openFile("one.txt")
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
            d2 = fd.writeChunk(0, b"lorem ipsum")
            d2.addCallback(cb_write2, fd)
            return d2

        d1 = self.fso.openFile("three.txt", os.O_CREAT | os.O_WRONLY)
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
            d2 = fd.writeChunk(0, b"dolor sit")
            d2.addCallback(cb_write2, fd)
            return d2

        d1 = self.fso.openFile("three.txt", os.O_CREAT | os.O_WRONLY)
        d1.addCallback(cb_write1)
        return d1

    def test_rename(self):
        d = self.fso.renameFile("one.txt", "eins.txt")
        d.addCallback(lambda _: self.assertDir(["eins.txt", "two.txt"]))
        return d

    def test_mkdir_rmdir(self):
        def cb_mkdir(_):
            self.assertDir(["one.txt", "two.txt", "adir"])
            d2 = self.fso.removeDirectory("adir")
            d2.addCallback(lambda _: self.assertDir(["one.txt", "two.txt"]))
            return d2

        d1 = self.fso.makeDirectory("adir")
        d1.addCallback(cb_mkdir)
        return d1

    def test_rmfile(self):
        d = self.fso.removeFile("two.txt")
        d.addCallback(lambda _: self.assertDir(["one.txt"]))
        return d

    def test_attrs(self):
        def cb_attrs2(r):
            self.assertEqual(r["mtime"], 4000)
            self.assertEqual(r["atime"], 4000)
            self.assertEqual(r["permissions"] & 0o777, 0o650)
            self.assertEqual(r["uid"], os.getuid())
            self.assertEqual(r["gid"], os.getgid())

        def cb_attrs1(_):
            d2 = self.fso.getAttrs("one.txt")
            d2.addCallback(cb_attrs2)
            return d2

        if platform.system() == "Windows":
            raise unittest.SkipTest("doesn't work on Windows")
        d1 = self.fso.setAttrs(
            "one.txt", {"mtime": 4000, "atime": 4000, "permissions": 0o650}
        )
        d1.addCallback(cb_attrs1)
        return d1

    def test_attrs_times(self):
        # on Windows we try only to set the file timestamps
        def cb_attrs2(r):
            self.assertEqual(r["mtime"], 4000)
            self.assertEqual(r["atime"], 4000)

        def cb_attrs1(_):
            d2 = self.fso.getAttrs("one.txt")
            d2.addCallback(cb_attrs2)
            return d2

        d1 = self.fso.setAttrs("one.txt", {"mtime": 4000, "atime": 4000})
        d1.addCallback(cb_attrs1)
        return d1

    def test_fattrs(self):
        def cb_attrs3(r, fd):
            self.assertEqual(r["mtime"], 4000)
            self.assertEqual(r["atime"], 4000)
            self.assertEqual(r["permissions"] & 0o777, 0o650)
            self.assertEqual(r["uid"], os.getuid())
            self.assertEqual(r["gid"], os.getgid())
            os.close(fd.fileno())

        def cb_attrs2(_, fd):
            d3 = fd.getAttrs()
            d3.addCallback(cb_attrs3, fd)
            return d3

        def cb_attrs1(fd):
            d2 = fd.setAttrs({"mtime": 4000, "atime": 4000, "permissions": 0o650})
            d2.addCallback(cb_attrs2, fd)
            return d2

        if platform.system() == "Windows":
            raise unittest.SkipTest("doesn't work on Windows")
        d1 = self.fso.openFile("one.txt", os.O_RDWR)
        d1.addCallback(cb_attrs1)
        return d1

    def test_realpath(self):
        def cb_realpath(r):
            if platform.system() == "Darwin" and r.startswith("/private"):
                # KLUDGE: Github test environment has odd virtual directory
                r = r[8:]
            self.assertEqual(r, os.path.join(self.tpath, "one.txt"))

        if platform.system() == "Windows":
            raise unittest.SkipTest("doesn't work on Windows")
        d = self.fso.realPath("./one.txt")
        d.addCallback(cb_realpath)
        return d

    def test_makelink(self):
        def cb_link(_):
            with open("one.lnk") as fd:
                self.assertEqual(fd.read(), "blahblahblah")

        d = self.fso.makeLink("one.lnk", "one.txt")
        d.addCallback(cb_link)
        return d

    def test_readlink(self):
        def cb_link2(r):
            self.assertEqual(r, os.path.join(self.tpath, "one.txt"))

        def cb_link1(_):
            d2 = self.fso.readLink("one.lnk")
            d2.addCallback(cb_link2)
            return d2

        if platform.system() == "Windows":
            raise unittest.SkipTest("doesn't work on Windows")
        d1 = self.fso.makeLink("one.lnk", "one.txt")
        d1.addCallback(cb_link1)
        return d1

    def test_listdir(self):
        def cb_listdir(r):
            r = list(r)
            self.assertDir([name for name, attrs in r])
            r = [attrs for name, attrs in r if name == "one.txt"]
            self.assertEqual(r[0]["mtime"], 4000)

        os.utime("one.txt", (4000, 4000))
        d1 = self.fso.openDirectory(".")
        d1.addCallback(cb_listdir)
        return d1

    def test_statfs(self):
        def cb_statfs(r):
            log.debug("statvfs: {vfs}", vfs=r)
            v = os.statvfs(".")
            self.assertEqual(r["size"], v.f_frsize)
            self.assertEqual(r["blocks"], v.f_blocks)
            self.assertTrue(abs(r["free"] - v.f_bavail) < 5)  # free blocks can change

        if not hasattr(os, "statvfs"):
            raise unittest.SkipTest("no statvfs on this platform")
        d1 = self.fso.statfs()
        d1.addCallback(cb_statfs)
        return d1

    def test_consumer(self):
        def cb_con2(_, fd, consumer):
            self.assertEqual(consumer.total_bytes, len(ONE_MEG_OF_BLAH))
            return fd.close()

        def cb_con1(fd):
            consumer = FakeConsumer()
            consumer.registerProducer(fd.producer, True)
            d2 = fd.send(consumer)
            d2.addCallback(cb_con2, fd, consumer)
            return d2

        with open("bigfile.txt", "w") as fd:
            fd.write(ONE_MEG_OF_BLAH)
        d1 = self.fso.openFile("bigfile.txt", os.O_CREAT | os.O_RDONLY)
        d1.addCallback(cb_con1)
        return d1

    def test_producer(self):
        def cb_pro2(_):
            s = os.stat("bigfile.txt")
            self.assertEqual(s.st_size, len(ONE_MEG_OF_BLAH))

        def cb_pro1(fd):
            producer = FakeProducer()
            consumer = fd.receive()
            consumer.registerProducer(producer, True)
            producer.fire(consumer)
            d2 = fd.close()
            d2.addCallback(cb_pro2)
            return d2

        d1 = self.fso.openFile("bigfile.txt", os.O_CREAT | os.O_WRONLY)
        d1.addCallback(cb_pro1)
        return d1


class TestThreadFs(BaseTestFs, unittest.TestCase):
    fso_class = asyncfs.ThreadFs
