# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.lore.man2lore}.
"""

from StringIO import StringIO

from twisted.trial.unittest import TestCase

from twisted.lore.man2lore import ManConverter


_TRANSITIONAL_XHTML_DTD = ("""\
<?xml version="1.0"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
""")


class ManConverterTestCase(TestCase):
    """
    Tests for L{ManConverter}.
    """

    def setUp(self):
        """
        Build instance variables useful for tests.

        @ivar converter: a L{ManConverter} to be used during tests.
        """
        self.converter = ManConverter()


    def assertConvert(self, inputLines, expectedOutput):
        """
        Helper method to check conversion from a man page to a Lore output.

        @param inputLines: lines of the manpages.
        @type inputLines: C{list}

        @param expectedOutput: expected Lore content.
        @type expectedOutput: C{str}
        """
        inputFile = StringIO()
        for line in inputLines:
            inputFile.write(line + '\n')
        inputFile.seek(0)
        outputFile = StringIO()
        self.converter.convert(inputFile, outputFile)
        self.assertEquals(
            outputFile.getvalue(), _TRANSITIONAL_XHTML_DTD + expectedOutput)


    def test_convert(self):
        """
        Test convert on a minimal example.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""', "Foo\n"]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<p>Foo\n\n</p>\n\n</body>\n</html>\n")
        self.assertConvert(inputLines, output)


    def test_TP(self):
        """
        Test C{TP} parsing.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""',
                ".SH HEADER",
                ".TP",
                "\\fB-o\\fR, \\fB--option\\fR",
                "An option"]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<h2>HEADER</h2>\n\n<dl><dt>"
                  "<strong>-o</strong>, <strong>--option</strong>\n</dt>"
                  "<dd>An option\n</dd>\n\n</dl>\n\n</body>\n</html>\n")
        self.assertConvert(inputLines, output)


    def test_TPMultipleOptions(self):
        """
        Try to parse multiple C{TP} fields.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""',
                ".SH HEADER",
                ".TP",
                "\\fB-o\\fR, \\fB--option\\fR",
                "An option",
                ".TP",
                "\\fB-n\\fR, \\fB--another\\fR",
                "Another option",
                ]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<h2>HEADER</h2>\n\n<dl><dt>"
                  "<strong>-o</strong>, <strong>--option</strong>\n</dt>"
                  "<dd>An option\n</dd>\n\n<dt>"
                  "<strong>-n</strong>, <strong>--another</strong>\n</dt>"
                  "<dd>Another option\n</dd>\n\n</dl>\n\n</body>\n</html>\n")
        self.assertConvert(inputLines, output)


    def test_TPMultiLineOptions(self):
        """
        Try to parse multiple C{TP} fields, with options text on several lines.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""',
                ".SH HEADER",
                ".TP",
                "\\fB-o\\fR, \\fB--option\\fR",
                "An option",
                "on two lines",
                ".TP",
                "\\fB-n\\fR, \\fB--another\\fR",
                "Another option",
                "on two lines",
                ]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<h2>HEADER</h2>\n\n<dl><dt>"
                  "<strong>-o</strong>, <strong>--option</strong>\n</dt>"
                  "<dd>An option\non two lines\n</dd>\n\n"
                  "<dt><strong>-n</strong>, <strong>--another</strong>\n</dt>"
                  "<dd>Another option\non two lines\n</dd>\n\n</dl>\n\n"
                  "</body>\n</html>\n")
        self.assertConvert(inputLines, output)


    def test_ITLegacyManagement(self):
        """
        Test management of BL/IT/EL used in some man pages.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""',
                ".SH HEADER",
                ".BL",
                ".IT An option",
                "on two lines",
                ".IT",
                "Another option",
                "on two lines",
                ".EL"
                ]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<h2>HEADER</h2>\n\n<dl>"
                  "<dt>on two lines\n</dt><dd>Another option\non two lines\n"
                  "</dd></dl>\n\n</body>\n</html>\n")
        self.assertConvert(inputLines, output)


    def test_interactiveCommand(self):
        """
        Test management of interactive command tag.
        """
        inputLines = ['.TH BAR "1" "Oct 2007" "" ""',
                ".SH HEADER",
                ".BL",
                ".IT IC foo AR bar",
                "option 1",
                ".IT IC egg AR spam OP AR stuff",
                "option 2",
                ".EL"
                ]
        output = ("<html><head>\n<title>BAR.1</title></head>\n<body>\n\n"
                  "<h1>BAR.1</h1>\n\n<h2>HEADER</h2>\n\n<dl>"
                  "<dt>foo <u>bar</u></dt><dd>option 1\n</dd><dt>egg "
                  "<u>spam</u> [<u>stuff</u>]</dt><dd>option 2\n</dd></dl>"
                  "\n\n</body>\n</html>\n")
        self.assertConvert(inputLines, output)
