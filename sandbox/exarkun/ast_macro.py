
import sys, copy, inspect, new

from compiler import walk, parse
from compiler import syntax, visitor, pycodegen, ast, misc
from compiler import consts, symbols, future

class MungeNames(visitor.ASTVisitor):
    def __init__(self, which):
        visitor.ASTVisitor.__init__(self)
        self.whichNames = which

    def visitName(self, node):
        if node.name in self.whichNames:
            node.name = '__macro_' + node.name
    visitAssName = visitName

class MacroExpander(visitor.ASTVisitor):

    def __init__(self, macros):
        visitor.ASTVisitor.__init__(self)
        self.macros = {}
        for (k, v) in macros.iteritems():
            source = inspect.getsource(v)
            macroAST = parse(source)

            func = macroAST.node.nodes[0]
            code = func.code
            body = code.nodes

            # Now replace all the argument name looks up with munged
            # name lookups.
            mn = MungeNames(func.argnames)
            walk(code, mn)

            self.macros[k] = body
        print self.macros

    def visitCallFunc(self, node, *args):
        if isinstance(node.node, ast.Name):
            args = node.args
            n = node.node.name
            replacement = self.macros.get(n)
            if replacement is not None:
                print 'Replacing'
                print
                print node
                print
                node.__class__ = ast.Stmt
                node.__dict__ = {'nodes': replacement}
                print node
                print

    def expand(self, f):
        filename = inspect.getsourcefile(f)
        source = file(filename).read()

        ast = parse(source)

        walk(ast, self)

        misc.set_filename(filename, ast)
        syntax.check(ast)

        from ast_pp import SourceWriter
        sw = SourceWriter()
        walk(ast, sw)

        gen = pycodegen.ModuleCodeGenerator(ast)
        gen.graph.setFlag(consts.CO_GENERATOR_ALLOWED)
        code = gen.getCode()

        d = {}
        exec code in d
        return d.get(f.func_name)

from twisted.internet import reactor, defer

def wait(d):
    yield d
    d = d.getResult()

def async():
    d = defer.Deferred()
    reactor.callLater(2, d.callback, "Foo!")
    return d

def simpleFunction():
    print wait(async())

def expandedAlready():
    d = async()
    yield d
    d = d.getResult()
    print d

def main():
    me = MacroExpander({'wait': wait})
    f = me.expand(simpleFunction)
    import dis
    dis.dis(f)

    reactor.callLater(1, f)
    reactor.run()

if __name__ == '__main__':
    main()

