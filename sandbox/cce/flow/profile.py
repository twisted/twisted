"""
    This basically shows that base.py#next() and wrap.py#_yield()
    consume .6 and 2.4 seconds (where the initial caller is .9)
    so, the overhead of the flow module is 3-4x without flow.
"""

from __future__ import generators
from twisted.flow import flow
import time

def nonFlow():
    def count(max):
        cnt = 0
        while cnt < max:
           cnt += 1
           yield cnt
    
    def middle(max):
        sum = 0
        itr = 0
        for x in count(max*1000):
            itr += 1
            sum += x
            if itr > max:
               yield sum
               sum = 0
               itr = 0
    
    def end(max):
        itr = 0
        for x in middle(max*10):
           itr += 1
           if itr > max:
               yield x
               itr = 0
   
      
    start = time.time()      
    for x in end(2):
        pass
    finish = time.time()
    return finish - start

def timeFlow():
    def count(max):
        cnt = 0
        while cnt < max:
           cnt += 1
           yield cnt
    
    def middle(max):
        sum = 0
        itr = 0
        f = flow.wrap(count(max*1000))
        yield f
        for x in f:
            itr += 1
            sum += x
            if itr > max:
               yield sum
               sum = 0
               itr = 0
            yield f
    
    def end(max):
        itr = 0
        f = flow.wrap(middle(max*10))
        yield f
        for x in f:
           itr += 1
           if itr > max:
               yield x
               itr = 0
           yield f
   
    start = time.time()      
    for x in flow.Block(end(2)):
        pass
    finish = time.time()
    return finish - start

import profile
profile.run('nonFlow()')
profile.run('timeFlow()')



#print "nonFlow", nonFlow()
#print "timeFlow", timeFlow()


