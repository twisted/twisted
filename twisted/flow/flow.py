# Twisted, the Framework of Your Internet
# Copyright (C) 2003 Matthew W. Lefkowitz
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
#
# Author: Clark Evans  (cce@clarkevans.com)
# 

""" flow -- asynchronous data flows using generators

    This module provides a mechanism for using async data flows through
    the use of generators.  The basic idea of flow is that when ever
    you require data from a producer, you yield the producer.  If the
    producer is ready, then you can call producer.next() to fetch the
    incoming data.  Otherwise, the underlying controller will suspend
    the operation to try again later.

    For example, here is a simple 'printer' which consumes items
    from its source by printing them.   Note that to get a new item,
    it first yields the data source and then calls source.next()

        from __future__ import generators
        from twisted.flow import flow
        from twisted.internet import reactor, defer
        
        def printer(source):
            source = flow.wrap(source)
            while True:
                yield source
                print source.next()
        
        someFlowSource =  ["one", flow.Cooperate(1), "two"]

        d = flow.Deferred(printer(someFlowSource))
        d.addCallback(lambda _: reactor.stop())
        reactor.run()
   
    In the example above, there are three objects imported from
    the flow module:

       flow.wrap        This converts many data sources such as lists,
                        generators, and deferreds, into a special 
                        instruction object, a Stage.   In this case,  
                        a simple list is wrapped.
     
       flow.Deferred    This is a flow Controller, which executes the
                        stage passed to it, aggregating all results into
                        a list which is passed to the deferred's callback.
                        In this case, the result list is empty, but the
                        callback is used to stop the reactor after the
                        printing has finished.

       flow.Cooperate   This is a special instruction object, which is
                        used by the flow Controller.  In this case, the
                        the flow pauses for one second between 'one'
                        and 'two'.

    Most classes in the flow module an Instruction, either a CallLater
    or a Stage.   A Stage instruction is used to wrap various sorts of
    producers, anything from a simple string to Callback functions.  
    Some stages can be constructed directly, such as Zip, Concurrent,
    Merge, Callback, or Threaded.  But in most cases, in particular
    _String, _List, _Iterable, and _Deferred, state construction is
    handled through the wrap function.  Stages can yield other stages 
    to build a processing chain, results which are returned to the 
    previous stage, or a CallLater instruction which causes the whole 
    operation to be suspended.   

    Typically, the CallLater instructions as passed up the call stack
    till the top level, or Controller.  The controller then typically
    returns control, but registers itself to be called later.  Once
    called again, the controller sets up the call stack and resumes
    the top level generator.  There is a special CallLater, Cooperate,
    which simply resumes the chain of stages at a later time.   Some 
    stages, Callback, _Deferred, and Threaded have their own special 
    CallLater which handles the process of resuming flow for their 
    specific case.

        Instruction
           CallLater
              Cooperate
           Stage
                  # private stages (use flow.wrap)
              _String
              _List
              _Iterable
              _Deferred
                  # public stages
              Map
                 Zip
              Concurrent
                 Merge
              Block
              Callback*
              Threaded*
        Controller
            Deferred 
            Block
            Protocol

"""

from twisted.flow.base import *
from twisted.flow.stage import *
from twisted.flow.pipe import *
from twisted.flow.wrap import wrap
from twisted.flow.controller import Deferred, Block
from twisted.flow.protocol import makeProtocol, Protocol
