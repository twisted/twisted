from __future__ import generators
from twisted.python.compat import StopIteration, iter
import flow

f = flow.Flow([1,2,3])
f.execute()
assert [1,2,3] == f.results

def producer():
    lst = flow.Generator([1,2,3])
    while 1: 
        yield lst;
        if lst.stop: 
            return
        yield lst.result
f = flow.Flow(producer())
f.execute()
assert [1,2,3] == f.results

def producer():
    lst = flow.Generator([1,2,3])
    nam = flow.Generator(['one','two','three'])
    while 1: 
        yield lst; yield nam
        if lst.stop or nam.stop:
            return
        yield (lst.result, nam.result)
f = flow.Flow(producer())
f.execute()
assert [(1,'one'),(2,'two'),(3,'three')] == f.results

def consumer():
    title = flow.Generator(['Title'])
    yield title
    yield title.getResult()
    lst = flow.Generator(producer())
    try:
        while 1:
            yield lst
            yield lst.getResult()
    except flow.StopIteration: pass

f = flow.Flow(consumer())
f.execute()
assert ['Title', (1,'one'),(2,'two'),(3,'three')] == f.results

from twisted.internet import reactor
def res(x):
    assert ['Title', (1,'one'),(2,'two'),(3,'three')] == x
f = flow.DeferredFlow(consumer())
f.addCallback(res)
reactor.iterate()
