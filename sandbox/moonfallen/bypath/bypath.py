import sys
import glob
import sre
import re
from xml.dom import minidom
from xml import xpath

class Program:
    def __init__(self, xmlfile):
        self.leading = ''
        self.python_buffer = []
        self.nodes = []
        self.xml = minidom.parse(xmlfile)
        self.namespace = {'document': self.xml}
        self.byp_scanner = sre.Scanner([
                (r'\s*$|\s*#.*', self.got_comment),
                (r'^node\s+.*:', self.got_expr),
                (r'^python\s*:', self.got_global),
                (r'.*', self.got_unknown),
                ])

        self.scanner = sre.Scanner([
                              (r'^\s+\S.*$', self.got_python),
                              (r'^\s*$', self.got_whiteLine),
                              (r'^.+$', self.got_byp),
                              ])
    def got_unknown(self, scanner, token):
        raise RuntimeError("Syntax error: %s" % (token,))
    def got_expr(self, scanner, token):
        xpath_expr = token[:-1].split(None, 1)[1].strip()
        self.nodes = xpath.Evaluate(xpath_expr, self.xml)
    def got_comment(self, scanner, _):
        pass
    def finishPython(self):
        source = '\n'.join(self.python_buffer)
        _g = self.namespace.copy()
        if len(source.strip()) > 0:
            compiled = compile(source, 'foo.byp', 'exec')
            if len(self.nodes) > 0:
                for node in self.nodes:
                    _g.update({'node': node})
                    eval(compiled, _g, {}) 
        self.python_buffer = []
        self.nodes = []

    def got_byp(self, scanner, token):
        self.finishPython()
        self.leading = ''
        self.byp_scanner.scan(token)

    def got_python(self, scanner, token):
        leading = re.findall('^\s+', token)[0]
        if self.leading == '':
            self.leading = leading
        elif len(leading) < len(self.leading):
            raise RuntimeError("Syntax error: change in indent %s" % (token,))
        self.python_buffer.append(token[len(self.leading):])

    def got_whiteLine(self, scanner, token):
        if len(self.python_buffer) > 0:
            self.python_buffer.append('')
    def got_global(self, scanner, token):
        print '*** global ***'

    def finish(self):
        self.finishPython()

def run(argv=None):
    if argv is None: argv = sys.argv
    bypfile , xmlfile = sys.argv[1:]
    txt = file(bypfile).read() 

    pr = Program(xmlfile)
    for line in txt.splitlines():
        # workaround sre.scanner which doesn't scan empty lines
        if line == '': line = '\n'
        pr.scanner.scan(line)
    pr.finish()
    return 0


if __name__ == '__main__':
    sys.exit(run())
