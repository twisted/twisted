# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Axista, Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General
# Public License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307
# USA

"""I am an data consumer driven by a state machine"""

(_FUNC_CONSUME,_FUNC_START,_FUNC_FINISH) = range(3)
class Flow:
    '''
       This is a data consumer driven by a state-machine

       Flow objects are used to dispatch data from a producer, 
       such as a database query, through various filter functions 
       until the data is eventually consumed. 

       As data is introduced into the Flow using the 'consume' 
       method, the Flow looks up the appropriate handler, and 
       calls it with the data provided.  If the callee wishes
       processing to continue, it responds with a (state,data)
       tuple, which is then used iteratively.  To stop the 
       flow, the callee simply returns None (the default).

       To have any effect, the Flow must have one or more 
       handlers which have been registered for each state.
       Only one handler is active for a given state at any
       time, thus this object uses the mapping key/value
       synax for handlers.
   '''
    def __init__(self, *bases):
        '''
           Initializes a Flow object, optionally using
           one or more subordinate flow objects for 
           default behavior.  
        '''
        self.states       = {}
        self.bases        = bases or []
        self.stack        = []
    #     
    def register(self, state, consumeHandler,
                 startHandler = None, finishHandler = None ):
        '''
            This allows the registration of callback functions
            which are applied whenever an appropriate event of
            a given state is encountered.
        '''
        self.states[state] = (consumeHandler, startHandler, finishHandler)
    #
    def _lookup(self,state,fnc=_FUNC_CONSUME):
        fncs = self.states.get(state,None)
        if not fncs:
            for base in self.bases:
                fncs  = base.states.get(state,None)
                if fncs: break
        if fncs: return fncs[fnc]
        errmsg = "\nstate '%s' not found for:%s"
        raise KeyError(errmsg % (state, str(self)))
    #
    def start(self,state):
        '''
           In some cases, hierarchical behavior is useful to 
           model; if the data flow is hierarchical, this is 
           used to mark the start of a branch.
        '''
        self.stack.append(state)
        fnc = self._lookup(state,_FUNC_START)
        if fnc: fnc()
    #
    def finish(self,state=None):
        val = self.stack.pop()
        if state: assert(state == val)
        fnc = self._lookup(val,_FUNC_FINISH)
        if fnc: fnc()
    #
    def consume(self,data,state='initial'):
        '''
           This is the primary dispatch loop which
           processes the data until the given handlers
           return Null
        '''
        while 1:
            nextConsumer = self._lookup(state)
            tpl = nextConsumer(data)
            if not(tpl): return
            state = tpl[0]
            data  = tpl[1]
            if len(tpl) > 2:  # fork
                arr = list(tpl[1:])
                self.start(state)
                while arr: self.consume(arr.pop(0),state)
                self.finish(state)
                return
    #
    def __str__(self,indlvl=0):
        indent = "\n" + "    " * indlvl
        indent2 = indent + "        "
        return "%sFlow: %s%s%s%s%s" % (
                  indent,repr(self),indent2, 
                  indent2.join(self.states.keys()),indent,
                  "".join(map(lambda a: a.__str__(indlvl+1), self.bases)))
    #
    def __setitem__(self,key,val): self.register(key,val)

#
# Following is just test code.
#
if '__main__' == __name__:

    def addOne(data):
        return "multiplyTwo", data+1
    def multiplyTwo(data):
        if data > 10:
            return "printResult", data*2
        else:
            return "addOne", data*2
    def printResult(data):
        print data
    
    f = Flow()
    f.register("initial", addOne)
    f.register("addOne", addOne)
    f.register("multiplyTwo", multiplyTwo)
    f.register("printResult", printResult)
    
    f.consume(1)
    f.consume(5)
    f.consume(11)
    
    
    def printHTML(data):
        print "<li>%s</li>" % data
    def startList():  print "<ul>"
    def finishList(): print "</ul>"
    
    fHTML = Flow(f)
    fHTML.register("printResult", printHTML, startList, finishList)
    
    fHTML.start("printResult")
    fHTML.consume(1)
    fHTML.consume(5)
    fHTML.consume(11)
    fHTML.finish("printResult")
    
    def forkBegin(data):
        return "printResult", data+1, data+2
    fFork = Flow(f)
    fFork.register("initial",forkBegin)
    
    fFork.consume(1)
    fFork.consume(5)
    fFork.consume(11)
    
    def foo(data):
        return "flarbis", data / 99
    
    
    bad = Flow(fFork)
    bad.register("initial", addOne)
    bad.register("multiplyTwo", foo)
    
    bad.consume(5)
