# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Tests for L{twisted.web.util.redirectTo}.
"""
from twisted.trial import unittest
from twisted.web.util import redirectTo
from twisted.web.test.requesthelper import DummyRequest

class RedirectHtmlEscapeTests(unittest.TestCase):
    def test_legitimate_redirect(self) -> None:
        """
        Test how redirectTo escapes legitimate URLs
        """
        request = DummyRequest([b""])
        html = redirectTo(b'https://twisted.org/', request)
        expected = b"""
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=https://twisted.org/\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <a href=\"https://twisted.org/\">click here</a>
    </body>
</html>
""" 
        self.assertEqual(html, expected)

    def test_malicious_redirect(self) -> None:
        """
        Test how redirectTo escapes redirect URLs containing HTML tags
        """
        request = DummyRequest([b""])
        html = redirectTo(b'https://twisted.org/"><script>alert(document.location)</script>', request)
        expected = b"""
<html>
    <head>
        <meta http-equiv=\"refresh\" content=\"0;URL=https://twisted.org/&quot;&gt;&lt;script&gt;alert(document.location)&lt;/script&gt;\">
    </head>
    <body bgcolor=\"#FFFFFF\" text=\"#000000\">
    <a href=\"https://twisted.org/&quot;&gt;&lt;script&gt;alert(document.location)&lt;/script&gt;\">click here</a>
    </body>
</html>
""" 
        self.assertEqual(html, expected)