from twisted.trial import unittest

from twisted.pb import referenceable

class URL(unittest.TestCase):
    def testURL(self):
        sr = referenceable.SturdyRef("pb://1234@localhost:9900/name")
        self.failUnlessEqual(sr.tubID, "1234")
        self.failUnlessEqual(sr.locationHints, ["localhost:9900"])
        self.failUnlessEqual(sr.name, "name")

    def testCompare(self):
        sr1 = referenceable.SturdyRef("pb://1234@localhost:9900/name")
        sr2 = referenceable.SturdyRef("pb://1234@localhost:9999/name")
        # only tubID and name matter
        self.failUnlessEqual(sr1, sr2)
        sr1 = referenceable.SturdyRef("pb://9999@localhost:9900/name")
        sr2 = referenceable.SturdyRef("pb://1234@localhost:9900/name")
        self.failIfEqual(sr1, sr2)
        sr1 = referenceable.SturdyRef("pb://1234@localhost:9900/name1")
        sr2 = referenceable.SturdyRef("pb://1234@localhost:9900/name2")
        self.failIfEqual(sr1, sr2)

    def testLocationHints(self):
        url = "pb://ABCD@localhost:9900,remote:8899/name"
        sr = referenceable.SturdyRef(url)
        self.failUnlessEqual(sr.tubID, "ABCD")
        self.failUnlessEqual(sr.locationHints, ["localhost:9900",
                                                "remote:8899"])
        self.failUnlessEqual(sr.name, "name")
