# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.
# -*- test-case-name: twisted.internet.test.test_async -*-
"""
This module contains asynchronous filesystem access functions and the threads-based implementation
"""

from typing import Tuple, Iterable, Optional, Callable, cast, Any
import os
import os.path
import threading

import attr
from zope.interface import implementer, providedBy

from twisted.internet import reactor
from twisted.python.filepath import FilePath
from twisted.internet.interfaces import (
    IPushProducer,
    IReactorFileAsync,
    FileAsyncFlags,
    IProducer,
    IConsumer,
    IAsyncReader,
    IAsyncWriter,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_BUFFER_MAX,
)
from twisted.python.threadpool import ThreadPool
from twisted.internet.threads import (
    deferToThreadPool,
    blockingCallFromThread,
)
from twisted.internet.defer import Deferred
from twisted.logger import Logger

log = Logger()


def openAsync(
    path: FilePath,
    flags: FileAsyncFlags,
    user_reactor: Any = None,
    pool: Optional[ThreadPool] = None,
) -> Deferred:
    """
    Open a file for asynchronous access

    @param flags: controls opening mode
    - B{READ} open the file for reading (all other flags imply writing)
    - B{OVERWRITE} the file is overwritten
    - B{TRUNCATE} the file is truncated
    - B{CREATE} create the file if it doesn't exist
    - B{EXCLUSIVE} create the file (if it exists already, error)and

    @param user_reactor: the reactor to use. If the reactor implements
    L{twisted.internet.interfaces.IReactorFileAsync} this is used,
    otherwise fallback to the threaded implementation.

    @param pool: the threadpool to use if threads are used. Default is the reactor's
    own threadpool. B{WARNING:} Reactor threadpools are generally for light work, you will
    usually need to provide a pool.

    @return: a Deferred returning L{IAsyncWriter} or L{IAsyncReader}
    """
    if not user_reactor:
        user_reactor = reactor
    if IReactorFileAsync in providedBy(user_reactor):  # pragma: no cover
        return user_reactor.openAsync(path, flags)
    if flags & FileAsyncFlags.READ:
        return ThreadFileReader.open(path, pool)
    return ThreadFileWriter.open(path, flags, pool)


def _deferToThread(pool, f: Callable, *args: Any, **kwargs: Any) -> Deferred:
    return cast(Deferred, deferToThreadPool(reactor, pool, f, *args, **kwargs))


@attr.s
@implementer(IAsyncReader)
class ThreadFileReader:
    """
    a file read asynchronously using threads.
    """

    _producer: "_ThreadFileProducer" = attr.ib()
    fd: int = attr.ib()
    pool: ThreadPool = attr.ib()

    @classmethod
    def open(cls, path: FilePath, pool: Optional[ThreadPool] = None):
        def int_open(fd, pool):
            return ThreadFileReader(fd=fd, pool=pool, producer=_ThreadFileProducer())

        if not pool:
            pool = reactor.getThreadPool()  # type: ignore
        real_path: str = path.path  # type: ignore
        d = _deferToThread(pool, os.open, real_path, os.O_RDONLY)
        d.addCallback(int_open, pool)
        return d

    def close(self) -> Deferred:
        return _deferToThread(self.pool, os.close, self.fd)

    def read(self, offset: int, length: int) -> Deferred:
        def int_read() -> bytes:
            os.lseek(self.fd, offset, 0)
            return os.read(self.fd, length)

        return _deferToThread(self.pool, int_read)

    def send(
        self, consumer: IConsumer, start: int = 0, chunkSize: int = DEFAULT_CHUNK_SIZE
    ) -> Deferred:
        self._producer.stop_flag = False
        self._producer.event.set()

        def int_read_loop() -> None:
            os.lseek(self.fd, start, 0)
            while True:
                buf = os.read(self.fd, chunkSize)
                if buf:
                    blockingCallFromThread(reactor, consumer.write, buf)
                if len(buf) < chunkSize or self._producer.stop_flag:
                    break
                self._producer.event.wait()

        return _deferToThread(self.pool, int_read_loop)

    def producer(self) -> "_ThreadFileProducer":
        return self._producer

    def fileno(self) -> int:
        return self.fd


@implementer(IAsyncWriter)
class ThreadFileWriter:
    def __init__(self, fd: int, pool: ThreadPool):
        self._open = True
        self._write_consumer: Optional["_ThreadFileConsumer"] = None
        self.fd = fd
        self.pool = pool

    @classmethod
    def open(
        cls, path: FilePath, flags: FileAsyncFlags, pool: Optional[ThreadPool] = None
    ):
        def int_open(fd, pool):
            return ThreadFileWriter(fd, pool)

        if not pool:
            pool = reactor.getThreadPool()  # type: ignore
        real_path: str = path.path  # type: ignore
        osflags = os.O_WRONLY
        if flags & FileAsyncFlags.CREATE:
            osflags |= os.O_CREAT
        if flags & FileAsyncFlags.TRUNCATE:
            osflags |= os.O_TRUNC
        if flags & FileAsyncFlags.EXCLUSIVE:
            osflags |= os.O_EXCL
        d = _deferToThread(pool, os.open, real_path, osflags)
        d.addCallback(int_open, pool)
        return d

    def close(self) -> Deferred:
        assert self._open, "don't close a ThreadFileWriter twice"
        self._open = False
        if self._write_consumer:
            self._write_consumer.close()
            d = self._write_consumer.write_deferred
            d.addCallback(lambda _: _deferToThread(self.pool, os.close, self.fd))
            return d
        else:
            return _deferToThread(self.pool, os.close, self.fd)

    def write(self, offset: int, data: bytes) -> Deferred:
        def int_write() -> int:
            os.lseek(self.fd, offset, 0)
            return os.write(self.fd, data)

        return _deferToThread(self.pool, int_write)

    def flush(self) -> Deferred:
        return _deferToThread(self.pool, os.fsync, self.fd)

    def receive(
        self, append: bool = False, buffer_max: int = DEFAULT_BUFFER_MAX
    ) -> IConsumer:
        self._write_consumer = _ThreadFileConsumer(self, append, buffer_max)
        return self._write_consumer

    def fileno(self) -> int:
        return self.fd


@implementer(IPushProducer)
class _ThreadFileProducer:
    def __init__(self) -> None:
        self.stop_flag = False
        self.event = threading.Event()

    def stopProducing(self) -> None:
        self.stop_flag = True

    def pauseProducing(self) -> None:
        self.event.clear()

    def resumeProducing(self) -> None:
        self.event.set()


@implementer(IConsumer)
class _ThreadFileConsumer:
    def __init__(
        self, thread_file: ThreadFileWriter, append: bool, buffer_max: int
    ) -> None:
        self.producer: Optional[IProducer] = None
        self.streaming = False
        self.lock = threading.Lock()
        self.event = threading.Event()
        self._paused = False
        self._buffer = bytearray()
        self.pool = thread_file.pool
        self.write_deferred = _deferToThread(
            self.pool, self._consumer_write_thread, append
        )
        self.fd = thread_file.fileno()
        self.buffer_max = buffer_max
        self._closed = False

    def registerProducer(self, producer: IProducer, streaming: bool) -> None:
        assert self.producer is None
        self.producer = producer
        self.streaming = streaming
        self._paused = False

    def unregisterProducer(self) -> None:
        assert self.producer
        if self.streaming and not self._paused:
            cast(IPushProducer, self.producer).pauseProducing()
            self._paused = True
        self.producer = None

    def write(self, data: bytes) -> None:
        with self.lock:
            self._buffer += data
            self.event.set()
        if (
            self.producer
            and self.streaming
            and (not self._paused)
            and len(self._buffer) > self.buffer_max
        ):
            cast(IPushProducer, self.producer).pauseProducing()
            self._paused = True

    def close(self) -> None:
        assert not self._closed, "don't close _ThreadFileConsumer twice"
        with self.lock:
            self._closed = True
            self.event.set()
        if self.producer and self.streaming and (not self._paused):
            cast(IPushProducer, self.producer).pauseProducing()
            self._paused = True

    def _consumer_write_thread(self, append: bool) -> None:
        os.lseek(self.fd, 0, os.SEEK_END if append else os.SEEK_SET)
        while True:
            with self.lock:
                buf = bytes(self._buffer)
                self._buffer = bytearray()
                if len(buf) == 0:
                    self.event.clear()
            if len(buf) == 0:
                if self._closed:
                    break
                if self.producer and (
                    (self.streaming and self._paused) or (not self.streaming)
                ):
                    self._paused = False
                    blockingCallFromThread(
                        reactor, cast(IPushProducer, self.producer).resumeProducing
                    )
                self.event.wait()
            else:
                os.write(self.fd, buf)
