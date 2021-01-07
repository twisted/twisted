# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details..

import os
import sys
import tempfile
import os.path
from twisted.protocols._smb import vfs
from twisted.trial import unittest
from unittest import skipUnless
from twisted.internet.defer import DeferredList
from twisted.logger import globalLogBeginner, textFileLogObserver, Logger

log = Logger()
observers = [textFileLogObserver(sys.stdout)]
globalLogBeginner.beginLoggingTo(observers)


class BaseTestVfs:
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
            os.unlink(i)
        os.chdir(self.oldpath)
        os.rmdir(self.tpath)
        self.fso.unregister()

    def assertDir(self, dlist):
        dlist.sort()
        self.assertEqual(sorted(os.listdir()), dlist)

    def test_open(self):
        d1 = self.fso.openFile("one.txt")
        d2 = self.fso.openFile("three.txt", os.O_CREAT | os.O_RDWR)
        d3 = DeferredList([d1, d2])
        d3.addCallback(lambda _: self.assertDir(["one.txt", "two.txt", "three.txt"]))
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

        d1 = self.fso.setAttrs(
            "one.txt", {"mtime": 4000, "atime": 4000, "permissions": 0o650}
        )
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

        d1 = self.fso.openFile("one.txt", os.O_RDWR)
        d1.addCallback(cb_attrs1)
        return d1

    def test_realpath(self):
        d = self.fso.realPath("./one.txt")
        d.addCallback(
            lambda r: self.assertEqual(r, os.path.join(self.tpath, "one.txt"))
        )
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
            self.assertEqual(r["free"], v.f_bavail)

        d1 = self.fso.statfs()
        d1.addCallback(cb_statfs)
        return d1


class TestThreadVfs(BaseTestVfs, unittest.TestCase):
    fso_class = vfs.ThreadVfs


@skipUnless(vfs.has_aio, "libaio not available")
class TestAIOVfs(BaseTestVfs, unittest.TestCase):
    fso_class = vfs.AIOVfs
