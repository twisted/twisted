
import sys, copy, inspect, new

from compiler import walk, parse
from compiler import syntax, visitor, pycodegen, ast, misc
from compiler import consts, symbols, future

class MacroExpander(visitor.ASTVisitor):

    def __init__(self, macros):
        visitor.ASTVisitor.__init__(self)
        self.macros = {}
        for (k, v) in macros.iteritems():
            source = inspect.getsource(v)
            macroAST = parse(source)
            body = macroAST.code.nodes
            self.macros[k] = body

    def visitCallFunc(self, node, *args):
        if isinstance(node.node, ast.Name):
            args = node.args
            n = node.node.name
            replacement = self.macros.get(n)
            if replacement is not None:
                node.__class__ = ast.Stmt
                node.__dict__ = {'nodes': replacement}

    def expand(self, f):
        filename = inspect.getsourcefile(f)
        source = inspect.getsource(f)
        ast = parse(source)

        # That gives us a module-sized AST.  We really don't want that.
        # This gives us a function-sized AST.
        func = ast.node.nodes[0]

        walk(func, self)

        misc.set_filename(filename, func)
        syntax.check(func)

        vis = symbols.SymbolVisitor()
        walk(ast, vis)
        scopes = vis.scopes

        ast.futures = future.find_futures(ast)

        gen = pycodegen.FunctionCodeGenerator(func, scopes, False, None, ast)
        gen.graph.setFlag(consts.CO_GENERATOR_ALLOWED)
        code = gen.getCode()

        # function(code, globals[, name[, argdefs[, closure]]])
        return new.function(code, sys.modules[f.__module__].__dict__,
                            f.func_name, inspect.getargspec(f),
                            f.func_closure)

def main():
    me = MacroExpander({})
    me.expand(main)()

if __name__ == '__main__':
    main()

