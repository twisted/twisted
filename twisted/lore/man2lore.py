# -*- test-case-name: twisted.lore.test.test_man2lore -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
man2lore: Converts man page source (i.e. groff) into lore-compatible html.

This is nasty and hackish (and doesn't support lots of real groff), but is good
enough for converting fairly simple man pages.
"""

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



class ManConverter(object):
    """
    Convert a man page to the Lore format.

    @ivar tp: State variable for handling text inside a C{TP} token. It can
        take values from 0 to 3:
            - 0: when outside of a C{TP} token.
            - 1: once a C{TP} token has been encountered. If the previous value
              was 0, a definition list is started. Then, at the first line of
              text, a definition term is started.
            - 2: when the first line after the C{TP} token has been handled.
              The definition term is closed, and a definition is started with
              the next line of text.
            - 3: when the first line as definition data has been handled.
    @type tp: C{int}
    """
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
        outf.flush()


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
        self.write(
            '<?xml version="1.0"?>\n'
            '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"\n'
            '    "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n')
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


    def macro_IC(self, line):
        cmd = line.split(' ', 1)[0]
        args = line[line.index(cmd) + len(cmd):]
        args = args.split(' ')
        text = cmd
        while args:
            arg = args.pop(0)
            if arg.lower() == "ar":
                text += " \\fU%s\\fR" % (args.pop(0),)
            elif arg.lower() == "op":
                ign = args.pop(0)
                text += " [\\fU%s\\fR]" % (args.pop(0),)

        self.text(text)


    def macro_TP(self, line):
        """
        Handle C{TP} token: start a definition list if it's first token, or
        close previous definition data.
        """
        if self.tp == 3:
            self.write('</dd>\n\n')
            self.tp = 1
        else:
            self.tp = 1
            self.write('<dl>')
            self.dl = 1


    def macro_BL(self, line):
        self.write('<dl>')
        self.tp = 1


    def macro_EL(self, line):
        if self.tp == 3:
            self.write('</dd>')
            self.tp = 1
        self.write('</dl>\n\n')
        self.tp = 0


    def macro_IT(self, line):
        if self.tp == 3:
            self.write('</dd>')
            self.tp = 1
        self.continueReceived(line)


    def text(self, line):
        """
        Handle a line of text without detected token.
        """
        if self.tp == 1:
            self.write('<dt>')
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
            elif bit[:2] == 'fU':
                # fU doesn't really exist, but it helps us to manage underlined
                # text.
                self.write('<u>' + escape(bit[2:]))
                self.state = 'u'
            elif bit[:3] == '(co':
                self.write('&copy;' + escape(bit[3:]))
            else:
                self.write(escape(bit))

        if self.tp == 1:
            self.write('</dt>')
            self.tp = 2
        elif self.tp == 2:
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
