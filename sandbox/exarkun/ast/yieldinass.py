#
# Yield in between an ass.
#

from compiler import ast, parse, pycodegen, misc

from twisted.internet import reactor, defer

def async(o):
    d = defer.Deferred()
    reactor.callLater(1, d.callback, o)
    return d

from defgen import waitForDeferred, deferredGenerator

s = """\
def g():
    x = waitForDeferred(async('g'))
g = deferredGenerator(g)
"""

mod = parse(s)
code = mod.node.nodes[0].code.nodes
ass = code[0]
expr = ass.expr
tempAss = ast.Assign([ast.AssName('__macro_temp', 'OP_ASSIGN')], expr)
code[0] = tempAss
code.insert(1, ast.Yield(ast.Name('__macro_temp')))
ass.expr = ast.Name('__macro_temp')
code.insert(2, ass)

misc.set_filename('<string>', mod)
cg = pycodegen.ModuleCodeGenerator(mod)
co = cg.getCode()

def f(x):
    print x
    print 'hoop hoop'
    return 

exec co in globals()
print g()
