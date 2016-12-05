# -*- test-case-name: twisted.python.test.test_htmlizer -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTML rendering of Python source.
"""

from twisted.python.compat import _tokenize, escape

import tokenize, keyword
from . import reflect

class TokenPrinter:

    currentCol, currentLine = 0, 1
    lastIdentifier = parameters = 0
    encoding = "utf-8"

    def __init__(self, writer):
        self.writer = writer


    def printtoken(self, type, token, sCoordinates, eCoordinates, line):
        if hasattr(tokenize, "ENCODING") and type == tokenize.ENCODING:
            self.encoding = token
            return

        (srow, scol) = sCoordinates
        (erow, ecol) = eCoordinates
        if self.currentLine < srow:
            self.writer('\n'*(srow-self.currentLine))
            self.currentLine, self.currentCol = srow, 0
        self.writer(' '*(scol-self.currentCol))
        if self.lastIdentifier:
            type = "identifier"
            self.parameters = 1
        elif type == tokenize.NAME:
            if keyword.iskeyword(token):
                type = 'keyword'
            else:
                if self.parameters:
                    type = 'parameter'
                else:
                    type = 'variable'
        else:
            type = tokenize.tok_name.get(type).lower()
        self.writer(token, type)
        self.currentCol = ecol
        self.currentLine += token.count('\n')
        if self.currentLine != erow:
            self.currentCol = 0
        self.lastIdentifier = token in ('def', 'class')
        if token == ':':
            self.parameters = 0



class HTMLWriter:

    noSpan = []

    def __init__(self, writer):
        self.writer = writer
        noSpan = []
        reflect.accumulateClassList(self.__class__, "noSpan", noSpan)
        self.noSpan = noSpan


    def write(self, token, type=None):
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        token = escape(token)
        token = token.encode("utf-8")
        if (type is None) or (type in self.noSpan):
            self.writer(token)
        else:
            self.writer(
                b'<span class="py-src-' + type.encode("utf-8") + b'">' +
                token + b'</span>')



class SmallerHTMLWriter(HTMLWriter):
    """
    HTMLWriter that doesn't generate spans for some junk.

    Results in much smaller HTML output.
    """
    noSpan = ["endmarker", "indent", "dedent", "op", "newline", "nl"]



def filter(inp, out, writer=HTMLWriter):
    out.write(b'<pre>')
    printer = TokenPrinter(writer(out.write).write).printtoken
    try:
        for token in _tokenize(inp.readline):
            (tokenType, string, start, end, line) = token
            printer(tokenType, string, start, end, line)
    except tokenize.TokenError:
        pass
    out.write(b'</pre>\n')



def main():
    import sys
    stdout = getattr(sys.stdout, "buffer", sys.stdout)
    with open(sys.argv[1], "rb") as f:
        filter(f, stdout)

if __name__ == '__main__':
    main()
