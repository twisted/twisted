
import sys
from twisted.python import log
log.startLogging(sys.stdout)

from StringIO import StringIO
from pprint import pprint
from compiler import parse, walk

class SourceWriter(object):
    _i = 0

    def __init__(self):
        self.s = StringIO()

    def w(self, s):
        self.s.write(s)

    def nl(self):
        self.s.write('\n')
        self.s.write(' ' * 4 * self._i)

    def indent(self):
        self._i += 1
        self.nl()

    def dedent(self):
        self._i -= 1
        self.nl()

    def visitModule(self, node):
        if node.doc is not None:
            self.wl(repr(node.doc))
        walk(node.node, self)

    def visitStmt(self, node):
        for n in node.getChildren():
            walk(n, self)

    def visitFunction(self, node):
        fmt = 'def %s(%s):'
        if node.defaults:
            nargs = len(node.argnames)
            ndefs = len(node.defaults)
            noDefaults = node.argnames[:nargs-ndefs]
            s = ', '.join(node.argnames[:noDefaults])
            if ndefs < nargs:
                argdefs = zip(node.argnames[noDefaults:], node.defaults)
                s = s + ', ' + ', '.join(['='.join(x) for x in argdefs])
        else:
            s = ', '.join(node.argnames)
        self.w(fmt % (node.name, s))
        self.indent()
        try:
            walk(node.code, self)
        finally:
            self.dedent()

    def visitAssign(self, node):
        walk(node.nodes[0], self)
        self.w(' = ')
        walk(node.expr, self)
        self.nl()

    def visitAssName(self, node):
        self.w(node.name)

    def visitCallFunc(self, node):
        walk(node.node, self)
        self.w('(')
        for a in node.args[:-1]:
            walk(a, self)
            self.w(', ')
        for a in node.args[-1:]:
            walk(a, self)
        self.w(')')
        self.nl()

    def visitListComp(self, node):
        self.w('[')
        walk(node.expr, self)
        for q in node.quals:
            walk(q, self)
        self.w(']')

    def visitListCompFor(self, node):
        self.w(' for ')
        walk(node.assign, self)
        self.w(' in ')
        walk(node.list, self)
        for expr in node.ifs:
            self.w(' if ')
            walk(expr, self)

    def visitName(self, node):
        self.w(node.name)

    def visitDiscard(self, node):
        walk(node.expr, self)

    def visitPrintnl(self, node):
        self.w('print ')
        if node.dest:
            self.w('>>')
            walk(node.dest, self)
            self.w(', ')
        for e in node.nodes:
            walk(e, self)
        self.nl()

    def visitGetattr(self, node):
        walk(node.expr, self)
        self.w('.')
        self.w(node.attrname)

    def visitImport(self, node):
        self.w('import ')
        for (mod, as) in node.names:
            self.w(mod)
            if as is not None:
                self.w(' as ')
                self.w(as)
            self.w(', ')
        self.nl()

    def visitFrom(self, node):
        self.w('from ')
        self.w(node.modname)
        self.w(' import ')
        for (mod, as) in node.names:
            self.w(mod)
            if as is not None:
                self.w(' as ')
                self.w(as)
            self.w(', ')
        self.nl()

    def visitConst(self, node):
        self.w(repr(node.value))

    def visitReturn(self, node):
        self.w('return ')
        walk(node.value, self)
        self.nl()

    def visitClass(self, node):
        self.w('class ')
        self.w(node.name)
        if node.bases:
            self.w('(')
            for b in node.bases:
                walk(b, self)
                self.w(', ')
            self.w('):')
        self.indent()
        try:
            if node.doc is not None:
                self.w(repr(node.doc))
            walk(node.code, self)
        finally:
            self.dedent()

    def visitAssAttr(self, node):
        walk(node.expr, self)
        self.w('.')
        self.w(node.attrname)

    def visitMul(self, node):
        walk(node.left, self)
        self.w(' * ')
        walk(node.right, self)

    def visitSub(self, node):
        walk(node.left, self)
        self.w(' - ')
        walk(node.right, self)

    def visitAdd(self, node):
        walk(node.left, self)
        self.w(' + ')
        walk(node.right, self)

    def visitMod(self, node):
        walk(node.left, self)
        self.w(' % ')
        walk(node.right, self)

    def visitAugAssign(self, node):
        walk(node.node, self)
        self.w(' ')
        self.w(node.op)
        self.w(' ')
        walk(node.expr, self)
        self.nl()

    def visitIf(self, node):
        keyword = 'if'
        for (cond, body) in node.tests:
            self.w(keyword)
            self.w(' ')
            walk(cond, self)
            self.w(':')
            self.indent()
            try:
                walk(body, self)
            finally:
                self.dedent()
            keyword = 'elif'
        if node.else_:
            self.w('else:')
            self.indent()
            try:
                walk(node.else_, self)
            finally:
                self.dedent()

    def visitCompare(self, node):
        walk(node.expr, self)
        for (op, arg) in node.ops:
            self.w(' ')
            self.w(op)
            self.w(' ')
            walk(arg, self)

    def visitFor(self, node):
        self.w('for ')
        walk(node.assign, self)
        self.w(' in ')
        walk(node.list, self)
        self.w(':')
        self.indent()
        try:
            walk(node.body, self)
        finally:
            self.dedent()
        if node.else_:
            self.w('else:')
            self.indent()
            try:
                walk(node.else_, self)
            finally:
                self.dedent()

    def visitSlice(self, node):
        walk(node.expr, self)
        self.w('[')
        if node.lower:
            walk(node.lower, self)
        self.w(':')
        if node.upper:
            walk(node.upper, self)
        self.w(']')

    def visitTuple(self, node):
        self.w('(')
        for expr in node.nodes:
            walk(expr, self)
            self.w(', ')
        self.w(')')

    def visitTryFinally(self, node):
        self.w('try:')
        self.indent()
        try:
            walk(node.body, self)
        finally:
            self.dedent()
        self.w('finally:')
        self.indent()
        try:
            walk(node.final, self)
        finally:
            self.dedent()

    def visitSubscript(self, node):
        walk(node.expr, self)
        self.w('[')
        walk(node.subs[0], self)
        self.w(']')

    def visitUnarySub(self, node):
        self.w('-')
        walk(node.expr, self)

    def visitAssTuple(self, node):
        self.w('(')
        for expr in node.nodes:
            walk(expr, self)
            self.w(', ')
        self.w(')')

    def visitRaise(self, node):
        self.w('raise ')
        walk(node.expr1, self)
        if node.expr2:
            self.w(', ')
            walk(node.expr2, self)
            if node.expr3:
                self.w(', ')
                walk(node.expr3, self)
        self.nl()

    def visitDict(self, node):
        self.w('{')
        for (k, v) in node.items:
            walk(k, self)
            self.w(':')
            walk(v, self)
            self.w(',')
        self.w('}')

    def __getattr__(self, name):
        raise AttributeError(name)

    def __str__(self):
        return self.s.getvalue()

def magic(s):
    ast = parse(s)
    sw = SourceWriter()
    walk(ast, sw)
    return ast, sw

if __name__ == '__main__':
    f = file(__file__, 'r').read()
    ast, sw = magic(f)
    print sw
    print ast
