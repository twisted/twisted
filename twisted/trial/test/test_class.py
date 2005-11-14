from twisted.trial import unittest

_setUpClassRuns = 0
_tearDownClassRuns = 0

class NumberOfRuns(unittest.TestCase):
    def setUpClass(self):
        global _setUpClassRuns
        _setUpClassRuns += 1
    
    def test_1(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def test_2(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def test_3(self):
        global _setUpClassRuns
        self.failUnlessEqual(_setUpClassRuns, 1)

    def tearDownClass(self):
        global _tearDownClassRuns
        self.failUnlessEqual(_tearDownClassRuns, 0)
        _tearDownClassRuns += 1


class AttributeSetUp(unittest.TestCase):
    def setUpClass(self):
        self.x = 42

    def setUp(self):
        self.failUnless(hasattr(self, 'x'), "Attribute 'x' not set")
        self.failUnlessEqual(self.x, 42)

    def test_1(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def test_2(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def tearDown(self):
        self.failUnlessEqual(self.x, 42) # still the same

    def tearDownClass(self):
        self.x = None


class AttributeManipulation(unittest.TestCase):
    def setUpClass(self):
        self.testsRun = 0

    def test_1(self):
        self.testsRun += 1

    def test_2(self):
        self.testsRun += 1

    def test_3(self):
        self.testsRun += 1

    def tearDown(self):
        self.failUnless(self.testsRun > 0)

    def tearDownClass(self):
        self.failUnlessEqual(self.testsRun, 3)


class AttributeSharing(unittest.TestCase):
    def test_1(self):
        if not hasattr(self, 'test2Run'):
            self.first = 'test1Run'
        else:
            self.failUnlessEqual(self.first, 'test2Run')
        self.test1Run = True

    def test_2(self):
        if not hasattr(self, 'test1Run'):
            self.first = 'test2Run'
        else:
            self.failUnlessEqual(self.first, 'test1Run')
        self.test2Run = True
        
