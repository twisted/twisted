#!/usr/bin/python

from twisted.protocols.sux import XMLParser
import os

class LatexSpitter(XMLParser):

    entities = { 'amp': '&', 'gt': '>', 'lt': '<', 'quot': '"', 'copy': '(C)'}

    ignoring = 0
    normalizing = 1

    def __init__(self, writer, currDir='.'):
        self.writer = writer
        self.currDir = currDir

    def gotTagStart(self, name, attributes):
        s = getattr(self, "mapStart_"+name, None)
        if s:
            self.writer(s)
        m = getattr(self, "start_"+name, None)
        m and m(name, attributes)

    def gotText(self, data):
        if self.ignoring:
            return
        if self.normalizing:
            data = ' '.join(data.split())+' '
        self.writer(data)

    def gotEntityReference(self, entityRef):
        self.writer(self.entities.get(entityRef, ''))

    def gotTagEnd(self, name):
        s = getattr(self, "mapEnd_"+name, None)
        if s:
            self.writer(s)
        m = getattr(self, "end_"+name, None)
        m and m(name)

    def _headerStart(self, h, attributes):
        level = int(h[1])-2
        self.writer('\\'+level*'sub'+'section{')

    def start_h1(self, _, _1):
        self.ignoring = 1

    def end_h1(self, _):
        self.ignoring = 0

    def start_pre(self, _, _1):
        self.normalizing = 0

    def end_pre(self, _):
        self.normalizing = 1

    def start_a(self, _, attrs):
        if attrs.get('class') == "py-listing":
            fileName = os.path.join(self.currDir, attrs['href'])
            self.writer('\\begin{verbatim}')
            self.writer(open(fileName).read())
            self.writer('\\end{verbatim}')
            self.ignoring = 1

    def end_a(self, _):
        self.ignoring = 0

    start_h2 = start_h3 = start_h4 = _headerStart
    mapStart_title = '\\title{'
    mapEnd_title = mapEnd_h2 = mapEnd_h3 = mapEnd_h4 = '}'

    mapStart_html = '\\documentclass{article}'
    mapStart_body = '\\begin{document}\n\\maketitle\n'
    mapEnd_body = '\\end{document}'

    mapStart_dl = mapStart_ul = '\\begin{itemize}'
    mapEnd_dl = mapEnd_ul = '\\end{itemize}'

    mapStart_ol = '\\begin{enumerate}'
    mapEnd_ol = '\\end{enumerate}'

    mapStart_li = '\\item '

    mapStart_dt = '\\item{'
    mapEnd_dt = '}'

    mapStart_p = '\n\n'

    mapStart_code = '\\verb@'
    mapEnd_code = '@'

    mapStart_pre = '\\begin{verbatim}'
    mapEnd_pre = '\\end{verbatim}'

    mapStart_em = '\\begin{em}'
    mapEnd_em = '\\end{em}'


def main():
    import sys
    f = open(sys.argv[1])
    fout = open(os.path.splitext(sys.argv[1])[0]+'.tex', 'w')
    spitter = LatexSpitter(fout.write, os.path.dirname(sys.argv[1]))
    spitter.makeConnection(None)
    spitter.dataReceived(f.read())

if __name__ == '__main__':
   main()
