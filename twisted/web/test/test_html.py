
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from twisted.trial.unittest import TestCase

from twisted.web import html


class HtmlTestCase(TestCase):
    def test_moduleMostlyDeprecated(self):
        """
        Calling L{PRE}, L{UL}, L{linkList} or L{output} results in a
        deprecation warning.
        """
        html.PRE('')
        html.UL([])
        html.linkList([])
        html.output(lambda: None)
        warnings = self.flushWarnings(
            offendingFunctions=[self.test_moduleMostlyDeprecated])
        for name, warning in zip(['PRE', 'UL', 'linkList', 'output'],
                                 warnings):
            self.assertEquals(
                warning['message'],
                "twisted.web.html.%s was deprecated in Twisted 11.0.0" % (
                    name,))
            self.assertEquals(warning['category'], DeprecationWarning)
        self.assertEquals(len(warnings), 4)
