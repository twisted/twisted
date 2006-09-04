from twisted.trial import unittest

from twisted.words.protocols.jabber import sasl_mechanisms

class PlainTest(unittest.TestCase):
    def testGetInitialResponse(self):
        """
        Test the initial response.
        """
        m = sasl_mechanisms.Plain(None, 'test', 'secret')
        self.assertEquals(m.getInitialResponse(), '\x00test\x00secret')



class DigestMD5Test(unittest.TestCase):
    def setUp(self):
        self.mechanism = sasl_mechanisms.DigestMD5('xmpp', 'example.org', None,
                                                   'test', 'secret')


    def testGetInitialResponse(self):
        """
        Test that no initial response is generated.
        """
        self.assertIdentical(self.mechanism.getInitialResponse(), None)
