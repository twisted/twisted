# Copyright (c) 2009-2011 Twisted Matrix Laboratories.
# See LICENSE for details.
"""
Tests for positioning sentences.
"""
import itertools
from zope.interface import classProvides

from twisted.positioning import base, ipositioning
from twisted.trial.unittest import TestCase


sentinelValueOne = "someStringValue"
sentinelValueTwo = "someOtherStringValue"



class DummyProtocol(object):
    """
    A simple, fake protocol.
    """
    classProvides(ipositioning.IPositioningSentenceProducer)

    @staticmethod
    def getSentenceAttributes():
        return ["type", sentinelValueOne, sentinelValueTwo]



class DummySentence(base.BaseSentence):
    """
    A sentence for L{DummyProtocol}.
    """
    ALLOWED_ATTRIBUTES = DummyProtocol.getSentenceAttributes()



class MixinProtocol(base.PositioningSentenceProducerMixin):
    """
    A simple, fake protocol that declaratively tells you the sentences
    it produces using L{base.PositioningSentenceProducerMixin}.
    """
    SENTENCE_CONTENTS = {
        None: [
            sentinelValueOne,
            sentinelValueTwo,
            None # see MixinTests.test_noNoneInSentenceAttributes
        ],
    }



class MixinSentence(base.BaseSentence):
    """
    A sentence for L{MixinProtocol}.
    """
    ALLOWED_ATTRIBUTES = MixinProtocol.getSentenceAttributes()



class SentenceTestsMixin:
    """
    Tests for positioning protocols and their respective sentences.
    """
    def test_attributeAccess(self):
        """
        Tests that accessing a sentence attribute gets the correct value, and
        accessing an unset attribute (which is specified as being a valid
        sentence attribute) gets C{None}.
        """
        thisSentinel = object()
        sentence = self.sentenceClass({sentinelValueOne: thisSentinel})
        self.assertEquals(getattr(sentence, sentinelValueOne), thisSentinel)
        self.assertEquals(getattr(sentence, sentinelValueTwo), None)


    def test_raiseOnMissingAttributeAccess(self):
        """
        Tests that accessing a nonexistant attribute raises C{AttributeError}.
        """
        sentence = self.sentenceClass({})
        self.assertRaises(AttributeError, getattr, sentence, "BOGUS")


    def test_raiseOnBadAttributeAccess(self):
        """
        Tests that accessing bogus attributes raises C{AttributeError}, *even*
        when that attribute actually is in the sentence data.
        """
        sentence = self.sentenceClass({"BOGUS": None})
        self.assertRaises(AttributeError, getattr, sentence, "BOGUS")


    sentenceType = "tummies"
    reprTemplate = "<%s (%s) {%s}>"


    def _expectedRepr(self, sentenceType="unknown type", dataRepr=""):
        """
        Builds the expected repr for a sentence.
        """
        clsName = self.sentenceClass.__name__
        return self.reprTemplate % (clsName, sentenceType, dataRepr)


    def test_unknownTypeRepr(self):
        """
        Test the repr of an empty sentence of unknown type.
        """
        sentence = self.sentenceClass({})
        expectedRepr = self._expectedRepr()
        self.assertEqual(repr(sentence), expectedRepr)


    def test_knownTypeRepr(self):
        """
        Test the repr of an empty sentence of known type.
        """
        sentence = self.sentenceClass({"type": self.sentenceType})
        expectedRepr = self._expectedRepr(self.sentenceType)
        self.assertEqual(repr(sentence), expectedRepr)



class DummyTests(TestCase, SentenceTestsMixin):
    """
    Tests for protocol classes that implement the appropriate interface
    (L{ipositioning.IPositioningSentenceProducer}) manually.
    """
    def setUp(self):
        self.protocol = DummyProtocol()
        self.sentenceClass = DummySentence



class MixinTests(TestCase, SentenceTestsMixin):
    """
    Tests for protocols deriving from L{base.PositioningSentenceProducerMixin}
    and their sentences.
    """
    def setUp(self):
        self.protocol = MixinProtocol()
        self.sentenceClass = MixinSentence


    def test_noNoneInSentenceAttributes(self):
        """
        Tests that C{None} does not appear in the sentence attributes of the
        protocol, even though it's in the specification.

        This is because C{None} is a placeholder for parts of the sentence you
        don't really need or want, but there are some bits later on in the
        sentence that you do want. The alternative would be to have to specify
        things like "_UNUSED0", "_UNUSED1"... which would end up cluttering
        the sentence data and eventually adapter state.
        """
        sentenceAttributes = self.protocol.getSentenceAttributes()
        self.assertNotIn(None, sentenceAttributes)
        
        sentenceContents = self.protocol.SENTENCE_CONTENTS
        sentenceSpecAttributes = itertools.chain(*sentenceContents.values())
        self.assertIn(None, sentenceSpecAttributes)
