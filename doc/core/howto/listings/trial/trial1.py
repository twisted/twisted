from twisted.trial import unittest

# note that here i put the setUp* methods before the tests
# and the tearDown* methods after, this is just for the point
# of illustration. Usually it is considered good style to put
# all of these classes together at the beginning of your 
# TestCase

class ExampleTest(unittest.TestCase):
    def setUpClass(self):
        print "run class-level initialization"
        self.counter = 0

    def setUp(self):
        print "\tbeginning test"
        
    def testZero(self):
        print "\t\ttestZero: %d" % (self.counter,)

    def testOne(self):
        print "\t\ttestOne: %d" % (self.counter,)

    def testTwo(self):
        print "\t\ttestTwo: %d" % (self.counter,)

    def tearDown(self):
        self.counter += 1

    def tearDownClass(self):
        print "clean up after class"



