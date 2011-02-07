# Copyright (c) 2001-2011 Twisted Matrix Laboratories.
# See LICENSE for details.

import re
import os

from twisted.trial import unittest
from twisted.internet.address import IPv4Address, UNIXAddress

try:
    os.symlink
except AttributeError:
    symlinkSkip = "Platform does not support symlinks"
else:
    symlinkSkip = None


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


    def test_hash(self):
        """
        C{__hash__} can be used to get a hash of an address, allowing
        addresses to be used as keys in dictionaries, for instance.
        """
        addr = self.buildAddress()
        d = {addr: True}
        self.assertTrue(d[self.buildAddress()])



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


    def test_comparisonOfLinkedFiles(self):
        """
        UNIXAddress objects compare as equal if they link to the same file.
        """
        linkName = self.mktemp()
        self.fd = open(self._socketAddress, 'w')
        os.symlink(os.path.abspath(self._socketAddress), linkName)
        self.assertTrue(
            UNIXAddress(self._socketAddress) == UNIXAddress(linkName))
    test_comparisonOfLinkedFiles.skip = symlinkSkip


    def test_hashOfLinkedFiles(self):
        """
        UNIXAddress Objects that compare as equal have the same hash value.
        """
        linkName = self.mktemp()
        self.fd = open(self._socketAddress, 'w')
        os.symlink(os.path.abspath(self._socketAddress), linkName)
        self.assertEquals(
            hash(UNIXAddress(self._socketAddress)), hash(UNIXAddress(linkName)))
    test_hashOfLinkedFiles.skip = symlinkSkip
