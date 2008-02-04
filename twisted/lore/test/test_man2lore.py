# Copyright (c) 2008 Twisted Matrix Laboratories.
# See LICENSE for details.


"""
Tests for L{twisted.lore.man2lore}.
"""

from StringIO import StringIO

from twisted.trial.unittest import TestCase

from twisted.lore.man2lore import ManConverter



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
        self.assertEquals(outputFile.getvalue(), expectedOutput)


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
