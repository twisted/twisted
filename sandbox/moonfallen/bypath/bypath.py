import sys
import glob
import sre
import re
from xml.dom import minidom
from xml import xpath

# sibling
import tpusage

class Options(tpusage.Options):
    synopsis = 'bypath [options] <bypfile> <xmlfile>'
    def parseArgs(self, bypfile, xmlfile):
        self['bypfile'] = bypfile
        self['xmlfile'] = xmlfile

class BaseEvaluator:
    namespace = {}
    def __init__(self, xml):
        BaseEvaluator.rememberNamespace({'document': xml})

    def evaluate(self, source, sourcename):
        if len(source.strip()) > 0:
            compiled = compile(source, sourcename, 'exec')
            self.internalEvaluate(compiled)

    def evalInNamespace(self, compiled, addlNamespace={}):
        _l = self.namespace.copy()
        _l.update(addlNamespace)
        eval(compiled, {}, _l)
        for k in addlNamespace:
            _l.pop(k, None)
        BaseEvaluator.rememberNamespace(_l)

    def rememberNamespace(cls, namespace):
        cls.namespace.update(namespace)
    rememberNamespace = classmethod(rememberNamespace)


class ExprEvaluator(BaseEvaluator):
    """Evaluator for node ...: blocks"""
    def __init__(self, xml, nodes):
        self.nodes = nodes
        BaseEvaluator.__init__(self, xml)
    def internalEvaluate(self,  compiled):
        if len(self.nodes) > 0:
            for node in self.nodes:
                self.evalInNamespace(compiled, {'node':node})

class PythonEvaluator(BaseEvaluator):
    """Evaluator for python ...: blocks"""
    def internalEvaluate(self, compiled):
        self.evalInNamespace(compiled)

class Program:
    def __init__(self, xmlfile):
        self.evaluator = None
        self.leading = ''
        self.python_buffer = []
        self.xml = minidom.parse(xmlfile)
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
        nodes = xpath.Evaluate(xpath_expr, self.xml)
        self.evaluator = ExprEvaluator(self.xml, nodes)
    def got_comment(self, scanner, _):
        pass
    def finishPython(self):
        source = '\n'.join(self.python_buffer)
        if self.evaluator is not None:
            self.evaluator.evaluate(source, 'FIXME')
            self.evaluator = None
        self.python_buffer = []

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
        """Vertical whitespace does affect Python syntax, so if we're in a
        Python block, add a white line.  For example, \ at the end of a line
        followed by whitespace is a syntax error.  Also vertical whitespace may
        be present in multiline strings.
        """
        if len(self.python_buffer) > 0:
            if len(token) < len(self.leading):
                self.python_buffer.append('')
            else:
                self.python_buffer.append(token[len(self.leading):])
    def got_global(self, scanner, token):
        self.evaluator = PythonEvaluator(self.xml)

    def finish(self):
        self.finishPython()

def run(argv=None):
    if argv is None: argv = sys.argv
    o = Options()
    try:
        o.parseOptions(argv[1:])
    except usage.UsageError, e:
        sys.stderr.write(str(o))
        sys.stderr.write('%s\n' % (str(e),))
        return 1

    txt = file(o['bypfile']).read() 

    pr = Program(o['xmlfile'])
    for line in txt.splitlines():
        # workaround sre.scanner which doesn't scan empty lines
        if line == '': line = '\n'
        pr.scanner.scan(line)
    pr.finish()
    return 0


if __name__ == '__main__':
    sys.exit(run())
