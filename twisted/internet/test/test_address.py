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


    def _stringRepresentation(self, stringFunction):
        """
        Verify that the string representation of an address object conforms to a
        simple pattern (the usual one for Python object reprs) and contains
        values which accurately reflect the attributes of the address.
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
        stringValue = stringFunction(addr)
        m = re.match(pattern, stringValue)
        self.assertNotEquals(
            None, m,
            "%s does not match the standard __str__ pattern "
            "ClassName(arg1, arg2, etc)" % (stringValue,))
        self.assertEquals(addr.__class__.__name__, m.group(1))

        args = [x.strip() for x in m.group(2).split(",")]
        self.assertEquals(
            args,
            [argSpec[1] % (getattr(addr, argSpec[0]),) for argSpec in self.addressArgSpec])


    def test_str(self):
        """
        C{str} can be used to get a string representation of an address instance
        containing information about that address.
        """
        self._stringRepresentation(str)


    def test_repr(self):
        """
        C{repr} can be used to get a string representation of an address
        instance containing information about that address.
        """
        self._stringRepresentation(repr)



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
