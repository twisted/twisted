# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

#
"""man2lore: Converts man page source (i.e. groff) into lore-compatible html.

This is nasty and hackish (and doesn't support lots of real groff), but is good
enough for converting fairly simple man pages.
"""
from __future__ import nested_scopes

import re, os
quoteRE = re.compile('"(.*?)"')

def escape(text):
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = quoteRE.sub('<q>\\1</q>', text)
    return text

def stripQuotes(s):
    if s[0] == s[-1] == '"':
        s = s[1:-1]
    return s

class ManConverter:
    state = 'regular'
    name = None
    tp = 0
    dl = 0
    para = 0

    def convert(self, inf, outf):
        self.write = outf.write
        longline = ''
        for line in inf.readlines():
            if line.rstrip() and line.rstrip()[-1] == '\\':
                longline += line.rstrip()[:-1] + ' '
                continue
            if longline:
                line = longline + line
                longline = ''
            self.lineReceived(line)
        self.closeTags()
        self.write('</body>\n</html>\n')

    def lineReceived(self, line):
        if line[0] == '.':
            f = getattr(self, 'macro_' + line[1:3].rstrip().upper(), None)
            if f:
                f(line[3:].strip())
        else:
            self.text(line)

    def continueReceived(self, cont):
        if not cont:
            return
        if cont[0].isupper():
            f = getattr(self, 'macro_' + cont[:2].rstrip().upper(), None)
            if f:
                f(cont[2:].strip())
        else:
            self.text(cont)

    def closeTags(self):
        if self.state != 'regular':
            self.write('</%s>' % self.state)
        if self.tp == 3:
            self.write('</dd>\n\n')
            self.tp = 0
        if self.dl:
            self.write('</dl>\n\n')
            self.dl = 0
        if self.para:
            self.write('</p>\n\n')
            self.para = 0

    def paraCheck(self):
        if not self.tp and not self.para:
            self.write('<p>')
            self.para = 1

    def macro_TH(self, line):
        self.write('<html><head>\n')
        parts = [stripQuotes(x) for x in line.split(' ', 2)] + ['', '']
        title, manSection = parts[:2]
        self.write('<title>%s.%s</title>' % (title, manSection))
        self.write('</head>\n<body>\n\n')
        self.write('<h1>%s.%s</h1>\n\n' % (title, manSection))
    
    macro_DT = macro_TH
    
    def macro_SH(self, line):
        self.closeTags()
        self.write('<h2>')
        self.para = 1
        self.text(stripQuotes(line))
        self.para = 0
        self.closeTags()
        self.write('</h2>\n\n')

    def macro_B(self, line):
        words = line.split()
        words[0] = '\\fB' + words[0] + '\\fR '
        self.text(' '.join(words))

    def macro_NM(self, line):
        if not self.name:
           self.name = line
        self.text(self.name + ' ')

    def macro_NS(self, line):
        parts = line.split(' Ns ')
        i = 0
        for l in parts:
            i = not i
            if i:
                self.text(l)
            else:
                self.continueReceived(l)

    def macro_OO(self, line):
        self.text('[')
        self.continueReceived(line)

    def macro_OC(self, line):
        self.text(']')
        self.continueReceived(line)

    def macro_OP(self, line):
        self.text('[')
        self.continueReceived(line)
        self.text(']')

    def macro_FL(self, line):
        parts = line.split()
        self.text('\\fB-%s\\fR' % parts[0])
        self.continueReceived(' '.join(parts[1:]))

    def macro_AR(self, line):
        parts = line.split()
        self.text('\\fI %s\\fR' % parts[0])
        self.continueReceived(' '.join(parts[1:]))

    def macro_PP(self, line):
        self.closeTags()

    def macro_TP(self, line):
        if self.tp == 3:
            self.write('</dd>\n\n')
        self.tp = 1

    def macro_BL(self, line):
        #assert self.tp == 0, self.tp
        self.write('<dl>')
        self.tp = 1

    def macro_EL(self, line):
        if self.tp == 3:
            self.write('</dd>')
            self.tp = 1
        #assert self.tp == 1, self.tp
        self.write('</dl>\n\n')
        self.tp = 0

    def macro_IT(self, line):
        if self.tp == 3:
            self.write('</dd>')
            self.tp = 1
        #assert self.tp == 1, (self.tp, line)
        self.write('\n<dt>')
        self.continueReceived(line)
        self.write('</dt>')
        self.tp = 2

    def text(self, line):
        if self.tp == 2:
            self.write('<dd>')
        self.paraCheck()

        bits = line.split('\\')
        self.write(escape(bits[0]))
        for bit in bits[1:]:
            if bit[:2] == 'fI':
                self.write('<em>' + escape(bit[2:]))
                self.state = 'em'
            elif bit[:2] == 'fB':
                self.write('<strong>' + escape(bit[2:]))
                self.state = 'strong'
            elif bit[:2] == 'fR':
                self.write('</%s>' % self.state)
                self.write(escape(bit[2:]))
                self.state = 'regular'
            elif bit[:3] == '(co':
                self.write('&copy;' + escape(bit[3:]))
            else:
                self.write(escape(bit))

        if self.tp == 2:
            self.tp = 3

class ProcessingFunctionFactory:

    def generate_lore(self, d, filenameGenerator=None):
        ext = d.get('ext', '.html')
        return lambda file,_: ManConverter().convert(open(file),
                                    open(os.path.splitext(file)[0]+ext, 'w'))

factory = ProcessingFunctionFactory()

if __name__ == '__main__':
    import sys
    mc = ManConverter().convert(open(sys.argv[1]), sys.stdout)
