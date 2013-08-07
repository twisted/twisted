# -*- test-case-name: twisted.names.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Serial Number Arithmetic

This module implements RFC 1982 DNS Serial Number Arithmetic
(see http://tools.ietf.org/pdf/rfc1982.pdf).
SNA is used in DNS and specifically in DNSSEC as defined in
RFC 4034 in the DNSSEC Signature Expiration and Inception Fields.

@author: Bob Novas
"""

import calendar, time



class SNA(object):
    """
    implements RFC 1982 - DNS Serial Number Arithmetic
    """
    serialBits = 32
    _modulo = 2 ** serialBits
    halfRing = 2 ** (serialBits-1)
    maxAdd = (2 ** (serialBits-1)-1)


    def __init__(self, number, serialBits=32):
        self.serialBits = serialBits

        self._modulo = 2 ** serialBits
        self.halfRing = 2 ** (serialBits - 1)
        self.maxAdd = (2 ** (serialBits - 1) - 1)

        self._number = int(number) % self._modulo


    def __repr__(self):
        return str(self._number)


    def asInt(self):
        """
        return an integer representing the object
        """
        return self._number


    def __eq__(self, sna2):
        """
        define the equality operator
        """
        return sna2._number == self._number


    def __lt__(self, sna2):
        """
        define the less than operator
        """
        return ((self != sna2) and
               ((self._number < sna2._number) and
                ((sna2._number - self._number) < self.halfRing) or
               (self._number > sna2._number) and
                ((self._number - sna2._number) > self.halfRing)))


    def __gt__(self, sna2):
        """
        define the greater than operator
        """
        return ((self != sna2) and
               ((self._number < sna2._number) and
               ((sna2._number - self._number) > self.halfRing) or
               (self._number > sna2._number) and
               ((self._number - sna2._number) < self.halfRing)))


    def __le__(self, sna2):
        """
        define the less than or equal operator
        """
        return self == sna2 or self < sna2


    def __ge__(self, sna2):
        """
        define the greater than or equal operator
        """
        return self == sna2 or self > sna2


    def __add__(self, sna2):
        """
        define the addition operator
        """
        if sna2 <= SNA(self.maxAdd):
            return SNA( (self._number + sna2._number) % self._modulo )
        else:
            raise ArithmeticError


    def __hash__(self):
        """
        define a hash function
        """
        return hash(self._number)



def snaMax(snaList):
    """
    takes a list of sna's from which it will pick the one
    with the highest value
    """
    if len(snaList) == 0:
        return None
    trialMax = snaList[0]
    for s in snaList[1:]:
        if not trialMax:
            trialMax = s
        elif s and s > trialMax:
            trialMax = s
    return trialMax



class DateSNA(SNA):
    """
    implements DNS Serial Number Arithmetic
    for dates 'YYYYMMDDHHMMSS' per RFC 4034 P3.1.5
    """
    fmt = '%Y%m%d%H%M%S'


    def __init__(self, utcDateTime=''):
        """
        accept a UTC date/time string as YYMMDDHHMMSS
        and convert it to seconds since the epoch
        """
        if not utcDateTime:
            utcDateTime = '19700101000000'
        dtstruct = time.strptime(utcDateTime, DateSNA.fmt)
        secondsSinceE = calendar.timegm(dtstruct)
        super(DateSNA, self).__init__(secondsSinceE)


    def __add__(self, sna2):
        """
        define the addition operator
        """
        if not isinstance(sna2, SNA):
            return NotImplemented

        if (sna2 <= SNA(self.maxAdd) and
            (self._number + sna2._number < self._modulo)):
            sna = SNA((self._number + sna2._number) % self._modulo)
            return DateSNA.fromSNA(sna)
        else:
            raise ArithmeticError


    def asDate(self):
        """return a representation of the object as a date string"""
        dtstruct = time.gmtime(self._number)
        return time.strftime(DateSNA.fmt, dtstruct)


    @classmethod
    def fromSNA(cls, sna):
        """
        create an DateSNA object from an SNA
        """
        d = cls()
        d._number = sna._number
        return d


    @classmethod
    def fromInt(cls, i):
        """
        create an DateSNA object from an int
        """
        return cls.fromSNA(SNA(i))


    def __str__(self):
        """
        return a string representation of the object
        """
        return self.asDate()
