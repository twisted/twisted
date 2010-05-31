# Copyright (c) 2001-2010 Twisted Matrix Laboratories.
# See LICENSE for details.

import re

from twisted.trial import unittest
from twisted.internet.address import IPv4Address, UNIXAddress

class AddressTestCaseMixin(object):
    def test_addressComparison(self):
        """
        Test that two different address instances, sharing the same
        properties are considered equal.
        """
        self.assertEquals(self.buildAddress(), self.buildAddress())


    def test_stringRepresentation(self):
        """
        Test that when addresses are converted to strings, they adhere to a
        standard pattern. Not sure if it's worth it, but seemed like a bit of
        fun and demonstrates an inconsistency with UNIXAddress.__str__
        """
        addr = self.buildAddress()
        pattern = "".join([
           "^",
           "([^\(]+Address)", # class name,
           "\(",       # opening bracket,
           "([^)]+)",  # arguments,
           "\)",       # closing bracket,
           "$"
        ])
        m = re.match(pattern, str(addr))
        self.assertNotEqual(None, m,
                            "%s does not match the standard __str__ pattern "
                            "ClassName(arg1, arg2, etc)" % str(addr))
        self.assertEqual(addr.__class__.__name__, m.group(1))

        args = [x.strip() for x in m.group(2).split(",")]
        self.assertEqual(len(args), len(self.addressArgSpec))
        def checkArg(arg, argSpec):
            self.assertEqual(argSpec[1] % getattr(addr, argSpec[0]), arg)
        map(checkArg, args, self.addressArgSpec)



class IPv4AddressTestCaseMixin(AddressTestCaseMixin):
    addressArgSpec = (("type", "%s"), ("host", "%r"), ("port", "%d"))



class IPv4AddressTCPTestCase(unittest.TestCase, IPv4AddressTestCaseMixin):
    def buildAddress(self):
        return IPv4Address("TCP", "127.0.0.1", 0)



class IPv4AddressUDPTestCase(unittest.TestCase, IPv4AddressTestCaseMixin):
    def buildAddress(self):
        return IPv4Address("UDP", "127.0.0.1", 0)



class UNIXAddressTestCase(unittest.TestCase, AddressTestCaseMixin):
    addressArgSpec = (("name", "%r"),)

    def setUp(self):
        self._socketAddress = self.mktemp()


    def buildAddress(self):
        return UNIXAddress(self._socketAddress)
