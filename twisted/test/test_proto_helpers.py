from twisted.test.proto_helpers import MemoryReactor
from twisted.trial import unittest



class TestMemoryReactor(unittest.TestCase):
    def test_readers(self):
        reader = object()
        reactor = MemoryReactor()

        reactor.addReader(reader)
        reactor.addReader(reader)

        self.assertEqual(reactor.getReaders(), [reader])

        reactor.removeReader(reader)

        self.assertEqual(reactor.getReaders(), [])

    def test_writers(self):
        writer = object()
        reactor = MemoryReactor()

        reactor.addWriter(writer)
        reactor.addWriter(writer)

        self.assertEqual(reactor.getWriters(), [writer])

        reactor.removeWriter(writer)

        self.assertEqual(reactor.getWriters(), [])
