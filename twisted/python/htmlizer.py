# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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

class TokenPrinter:

    def __init__(self, writer):
        self.currentCol, self.currentLine = 0, 1
        self.writer = writer

    def printtoken(self, type, token, (srow, scol), (erow, ecol), line):
        if self.currentLine < srow:
            self.writer('\n'*(srow-self.currentLine))
            self.currentLine, self.currentCol = srow, 0
        self.writer(' '*(scol-self.currentCol))
        self.writer(token, type)
        self.currentCol = ecol
        self.currentLine += token.count('\n')
        if token.count('\n'):
            self.currentCol = 0
       

class HTMLWriter:

    def __init__(self, writer):
        self.writer = writer

    def write(self, token, type=None):
        token = cgi.escape(token)
        if type is None:
            self.writer(token)
        else:
            if type == tokenize.NAME:
                if keyword.kwdict.has_key(token):
                    type = 'keyword'
                else:
                    type = 'identifier'
            else:
                type = tokenize.tok_name[type].lower()
            self.writer('<span class="py-src-%s">%s</span>' %
                        (type, token))
       

def filter(inp, out):
    out.write('<pre>\n')
    printer = TokenPrinter(HTMLWriter(out.write).write).printtoken
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
