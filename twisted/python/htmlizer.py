# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2004 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
import tokenize, cgi, keyword
import reflect

class TokenPrinter:

    currentCol, currentLine = 0, 1
    lastIdentifier = parameters = 0

    def __init__(self, writer):
        self.writer = writer

    def printtoken(self, type, token, (srow, scol), (erow, ecol), line):
        if self.currentLine < srow:
            self.writer('\n'*(srow-self.currentLine))
            self.currentLine, self.currentCol = srow, 0
        self.writer(' '*(scol-self.currentCol))
        if self.lastIdentifier:
            type = "identifier"
            self.parameters = 1
        elif type == tokenize.NAME:
             if keyword.kwdict.has_key(token):
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
        if token.count('\n'):
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
        token = cgi.escape(token)
        if (type is None) or (type in self.noSpan):
            self.writer(token)
        else:
            self.writer('<span class="py-src-%s">%s</span>' %
                        (type, token))


class SmallerHTMLWriter(HTMLWriter):
    """HTMLWriter that doesn't generate spans for some junk.

    Results in much smaller HTML output.
    """
    noSpan = ["endmarker", "indent", "dedent", "op", "newline", "nl"]

def filter(inp, out, writer=HTMLWriter):
    out.write('<pre>\n')
    printer = TokenPrinter(writer(out.write).write).printtoken
    try:
        tokenize.tokenize(inp.readline, printer)
    except tokenize.TokenError:
        pass
    out.write('</pre>\n')

def main():
    import sys
    filter(open(sys.argv[1]), sys.stdout)

if __name__ == '__main__':
   main()
