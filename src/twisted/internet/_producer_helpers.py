# -*- test-case-name: twisted.protocols.test.test_tls,twisted.web.test.test_http2 -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Helpers for working with producers.
"""

from typing import List

from zope.interface import implementer

from twisted.internet.interfaces import IPushProducer
from twisted.internet.task import cooperate
from twisted.logger import Logger

_log = Logger()

# This module exports nothing public, it's for internal Twisted use only.
__all__: List[str] = []


@implementer(IPushProducer)
class _PullToPush:
    """
    An adapter that converts a non-streaming to a streaming producer.

    Because of limitations of the producer API, this adapter requires the
    cooperation of the consumer. When the consumer's C{registerProducer} is
    called with a non-streaming producer, it must wrap it with L{_PullToPush}
    and then call C{startStreaming} on the resulting object. When the
    consumer's C{unregisterProducer} is called, it must call
    C{stopStreaming} on the L{_PullToPush} instance.

    If the underlying producer throws an exception from C{resumeProducing},
    the producer will be unregistered from the consumer.

    @ivar _producer: the underling non-streaming producer.

    @ivar _consumer: the consumer with which the underlying producer was
                     registered.

    @ivar _finished: C{bool} indicating whether the producer has finished.

    @ivar _coopTask: the result of calling L{cooperate}, the task driving the
                     streaming producer.
    """

    _finished = False

    def __init__(self, pullProducer, consumer):
        self._producer = pullProducer
        self._consumer = consumer

    def _pull(self):
        """
        A generator that calls C{resumeProducing} on the underlying producer
        forever.

        If C{resumeProducing} throws an exception, the producer is
        unregistered, which should result in streaming stopping.
        """
        while True:
            with _log.failuresHandled(
                "while calling resumeProducing on {producer}", producer=self._producer
            ) as op:
                self._producer.resumeProducing()
            if op.failed:
                with _log.failuresHandled(
                    "while calling unregisterProducer on {consumer}",
                    consumer=self._consumer,
                ) as handlingop:
                    self._consumer.unregisterProducer()
                if handlingop.failed:
                    # The consumer should now call stopStreaming() on us,
                    # thus stopping the streaming.
                    self._finished = True
                    return
            yield None

    def startStreaming(self):
        """
        This should be called by the consumer when the producer is registered.

        Start streaming data to the consumer.
        """
        self._coopTask = cooperate(self._pull())

    def stopStreaming(self):
        """
        This should be called by the consumer when the producer is
        unregistered.

        Stop streaming data to the consumer.
        """
        if self._finished:
            return
        self._finished = True
        self._coopTask.stop()

    def pauseProducing(self):
        """
        @see: C{IPushProducer.pauseProducing}
        """
        self._coopTask.pause()

    def resumeProducing(self):
        """
        @see: C{IPushProducer.resumeProducing}
        """
        self._coopTask.resume()

    def stopProducing(self):
        """
        @see: C{IPushProducer.stopProducing}
        """
        self.stopStreaming()
        self._producer.stopProducing()
