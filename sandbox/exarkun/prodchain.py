# -*- coding: Latin-1 -*-

"""A class for combining multiple producers easily."""

from __future__ import generators

from twisted.internet import interfaces

class ProducerChain:
    """Jam a pile of producers down a consumer's throat.
    
    Producers must have a "finishedProducing" attribute that is true
    once they have no more data to produce.
    """
    __implements__ = (interfaces.IProducer,)

    _onDone = None

    def beginProducing(self, consumer, producers):
        assert not self._onDone
        self.consumer = consumer
        self.producers = iter(producers)
        
        self.prod = producers.next()
        self.prod.produce = self.produce.write
        self._onDone = defer.Deferred()
        self.consumer.registerProducer(self, False)
        return self._onDone

    def resumeProducing(self):
        self.prod.resumeProducing()
        if getattr(self.prod, 'finishedProducing', False):
            try:
                self.prod = self.producers.next()
            except StopIteration:
                self.consumer.unregisterProducer()
                self._onDone.callback(self)
                self._onDone = self.consumer = self.prod = None
            else:
                self.prod.produce = self.consumer.write

    def pauseProducing(self):
        pass

    def stopProducing(self):
        if self._onDone:
            self._onDone.errback(Exception())
            self._onDone = None

class StringProducer:
    finishedProducing = False
    
    def __init__(self, s):
        self.s = s
    
    def resumeProducing(self):
        self.finishedProducing = True
        self.produce(self.s)
        self.s = None

class FileProducer:
    CHUNK_SIZE = 2 ** 2 ** 2 ** 2
    finishedProducing = False
    
    def __init__(self, f):
        self.f = f
    
    def resumeProducing(self):
        b = self.f.read(self.CHUNK_SIZE)
        if not b:
            self.finishedProducing = True
            self.f = None
        else:
            self.produce(b)

def collapseNestedLists(items):
    """Turn a nested list structure into an iterable of Producers.

    Strings in C{items} will be sent as literals if they contain CR or LF,
    otherwise they will be quoted.  References to None in C{items} will be
    translated to the atom NIL.  Objects with a 'read' attribute will have
    it called on them with no arguments and the returned string will be
    inserted into the output as a literal.  Integers will be converted to
    strings and inserted into the output unquoted.  Instances of
    C{DontQuoteMe} will be converted to strings and inserted into the output
    unquoted.
    
    This function used to be much nicer, and only quote things that really
    needed to be quoted (and C{DontQuoteMe} did not exist), however, many
    broken IMAP4 clients were unable to deal with this level of sophistication,
    forcing the current behavior to be adopted for practical reasons.

    @type items: Any iterable

    @rtype: C{str}
    """
    pieces = []
    for i in items:
        if i is None:
            pieces.extend([' ', 'NIL'])
        elif isinstance(i, (DontQuoteMe, int, long)):
            pieces.extend([' ', str(i)])
        elif isinstance(i, types.StringTypes):
            if _needsLiteral(i):
                pieces.extend([' ', '{', str(len(i)), '}', IMAP4Server.delimiter, i])
            else:
                pieces.extend([' ', _quote(i)])
        elif hasattr(i, 'read'):
            pieces.extend([' ', '{', str(len(d)), '}', IMAP4Server.delimeter])
            yield StringProducer(''.join(pieces[1:]))
            yield FileProducer(i)
            pieces = []
        else:
            pieces.extend([' ', '(%s)' % (collapseNestedLists(i),)])
    if pieces:
        yield StringProducer(''.join(pieces[1:]))
