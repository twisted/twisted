# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTTP errors.
"""

from twisted.trial import unittest
from twisted.web import error

class ErrorTestCase(unittest.TestCase):
    """
    Tests for how L{Error} attributes are initialized.
    """
    def test_noMessageValidStatus(self):
        """
        If no C{message} argument is passed to the L{Error} constructor and the
        C{code} argument is a valid HTTP status code, C{code} is mapped to a
        descriptive string to which C{message} is assigned.
        """
        e = error.Error("200")
        self.assertEqual(e.message, "OK")


    def test_noMessageInvalidStatus(self):
        """
        If no C{message} argument is passed to the L{Error} constructor and
        C{code} isn't a valid HTTP status code, C{message} stays C{None}.
        """
        e = error.Error("InvalidCode")
        self.assertEqual(e.message, None)


    def test_messageExists(self):
        """
        If a C{message} argument is passed to the L{Error} constructor, the
        C{message} isn't affected by the value of C{status}.
        """
        e = error.Error("200", "My own message")
        self.assertEqual(e.message, "My own message")



class PageRedirectTestCase(unittest.TestCase):
    """
    Tests for how L{PageRedirect} attributes are initialized.
    """
    def test_noMessageValidStatus(self):
        """
        If no C{message} argument is passed to the L{PageRedirect} constructor
        and the C{code} argument is a valid HTTP status code, C{code} is mapped
        to a descriptive string to which C{message} is assigned.
        """
        e = error.PageRedirect("200", location="/foo")
        self.assertEqual(e.message, "OK to /foo")


    def test_noMessageValidStatusNoLocation(self):
        """
        If no C{message} argument is passed to the L{PageRedirect} constructor
        and C{location} is also empty and the C{code} argument is a valid HTTP
        status code, C{code} is mapped to a descriptive string to which
        C{message} is assigned without trying to include an empty location.
        """
        e = error.PageRedirect("200")
        self.assertEqual(e.message, "OK")


    def test_noMessageInvalidStatusLocationExists(self):
        """
        If no C{message} argument is passed to the L{PageRedirect} constructor
        and C{code} isn't a valid HTTP status code, C{message} stays C{None}.
        """
        e = error.PageRedirect("InvalidCode", location="/foo")
        self.assertEqual(e.message, None)


    def test_messageExistsLocationExists(self):
        """
        If a C{message} argument is passed to the L{PageRedirect} constructor,
        the C{message} isn't affected by the value of C{status}.
        """
        e = error.PageRedirect("200", "My own message", location="/foo")
        self.assertEqual(e.message, "My own message to /foo")


    def test_messageExistsNoLocation(self):
        """
        If a C{message} argument is passed to the L{PageRedirect} constructor
        and no location is provided, C{message} doesn't try to include the empty
        location.
        """
        e = error.PageRedirect("200", "My own message")
        self.assertEqual(e.message, "My own message")



class InfiniteRedirectionTestCase(unittest.TestCase):
    """
    Tests for how L{InfiniteRedirection} attributes are initialized.
    """
    def test_noMessageValidStatus(self):
        """
        If no C{message} argument is passed to the L{InfiniteRedirection}
        constructor and the C{code} argument is a valid HTTP status code,
        C{code} is mapped to a descriptive string to which C{message} is
        assigned.
        """
        e = error.InfiniteRedirection("200", location="/foo")
        self.assertEqual(e.message, "OK to /foo")


    def test_noMessageValidStatusNoLocation(self):
        """
        If no C{message} argument is passed to the L{InfiniteRedirection}
        constructor and C{location} is also empty and the C{code} argument is a
        valid HTTP status code, C{code} is mapped to a descriptive string to
        which C{message} is assigned without trying to include an empty
        location.
        """
        e = error.InfiniteRedirection("200")
        self.assertEqual(e.message, "OK")


    def test_noMessageInvalidStatusLocationExists(self):
        """
        If no C{message} argument is passed to the L{InfiniteRedirection}
        constructor and C{code} isn't a valid HTTP status code, C{message} stays
        C{None}.
        """
        e = error.InfiniteRedirection("InvalidCode", location="/foo")
        self.assertEqual(e.message, None)


    def test_messageExistsLocationExists(self):
        """
        If a C{message} argument is passed to the L{InfiniteRedirection}
        constructor, the C{message} isn't affected by the value of C{status}.
        """
        e = error.InfiniteRedirection("200", "My own message", location="/foo")
        self.assertEqual(e.message, "My own message to /foo")


    def test_messageExistsNoLocation(self):
        """
        If a C{message} argument is passed to the L{InfiniteRedirection}
        constructor and no location is provided, C{message} doesn't try to
        include the empty location.
        """
        e = error.InfiniteRedirection("200", "My own message")
        self.assertEqual(e.message, "My own message")
