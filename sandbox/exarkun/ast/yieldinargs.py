
from compiler import ast, misc, parse, pycodegen

n = """
def foo():
    def bar(x, y):
        print 'bar', x, y
    x = 1
    yield x
"""

foo = parse(n)

m = """
bar(1.0, 1j)
"""

bar = parse(m)

bar.node.nodes[0].expr.args.insert(1, ast.Yield(ast.Name('bar')))
foo.node.nodes[0].code.nodes.append(bar.node.nodes[0].expr)

misc.set_filename('<string>', foo)

cg = pycodegen.ModuleCodeGenerator(foo)
co = cg.getCode()

d = {}
exec co in d
g = d['foo']()
print g.next()
print g.next()
print g.next()
