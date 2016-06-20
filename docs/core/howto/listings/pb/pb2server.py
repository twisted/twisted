#!/usr/bin/env python

# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

from twisted.spread import pb
from twisted.internet import reactor

class Two(pb.Referenceable):
    def remote_print(self, arg):
        print("two.print was given", arg)
        
class One(pb.Root):
    def __init__(self, two):
        #pb.Root.__init__(self)   # pb.Root doesn't implement __init__
        self.two = two
    def remote_getTwo(self):
        print("One.getTwo(), returning my two called", self.two)
        return self.two
    def remote_checkTwo(self, newtwo):
        print("One.checkTwo(): comparing my two", self.two)
        print("One.checkTwo(): against your two", newtwo)
        if self.two == newtwo:
            print("One.checkTwo(): our twos are the same")
        

two = Two()
root_obj = One(two)
reactor.listenTCP(8800, pb.PBServerFactory(root_obj))
reactor.run()
