# TODO:
# failure detection
# voluntary delinking
# successor list
# HyperChord


import random
import sha
import socket
import struct
from twisted.spread import pb

NBIT = 160    # Size (in bits) of Chord identifiers
vNodes = 1    # sure hope you dont want more than 256.        

def between(n, a, b):
    """Check if n in interval(a, b) on the circle."""
    if   a == b: return n != a			# n is the only node not in (n, n)
    elif a < b: return n > a and n < b
    else: return n > a or n < b

def betweenL(n, a, b):
    """Check if n in interval[a, b) on the circle."""
    if a == b and n == a: return 1
    elif a < b: return n >= a and n < b
    else: return n >= a or n < b

def betweenR(n, a, b):
    """Check if n in interval(a, b] on the circle."""
    if a == b and n == a: return 1
    elif a < b: return n > a and n <= b
    else: return n > a or n <= b

class Node(pb.Copyable, pb.Perspective):
    """A node in a Chord network."""
    def __init__(self, address, perspectiveName, identityName, port=pb.portno):
        global vNodes
        pb.Perspective.__init__(self, perspectiveName, identityName) 
        self.id = sha.new(socket.inet_aton(address) + struct.pack('!h', port) + chr(vNodes)).digest()
        self.address = (address, port, vNodes)
        vNodes = vNodes + 1
        self.finger = [None] * (NBIT+1)
        self.lastFixed = 1  # Needed for fixFingers
        self.pred = None
    
    def getStateToCopyFor(self, persp):
            return {"id": self.id, "address": self.address}

    def __repr__(self):
        return "<Node " + `self.id` + ">"
    
    def join(self, n2):
        """Intialize finger tables of local node.
        n2 is a node already on the network or None if we're the first."""
        if n2:
            n2.findSuccessor(self.id).addCallback(lambda x: self.getNodeAt(x).addCallback(iHatePython, callbackArgs=(1,)))
            self.finger[1].notify(self.address, pbanswer=0)
            self.findPredecessor(self.id).addCallback(iHatePython2)
            for i in range(1, NBIT):
                if betweenL(self.id, self.start(i+1), 
                  self.finger[i].id):
                    self.finger[i+1] = self.finger[i]
                else:
                    n2.findSuccessor(self.start(i+1)).addCallback(lambda x: self.getNodeAt(x).addCallback(iHatePython, callbackArgs=(i+1,)))
            n2.notify(self.address, pbanswer=0)
        else:
            self.finger[1] = None
            self.pred = None

    def iHatePython(self, x, i):
        #CRUM! DEFEATED BY DISTANCE
        self.finger[i] = x
    def iHatePython2(self, n):
        #ALSO TOO FAR!
        self.pred = n

    def perspective_getSuccessor(self):
        return self.finger[1]
    def perspective_getPredecessor(self):
        return self.pred
    
    def perspective_findSuccessor(self, id):
        self.findPredecessor(id).addCallback(findSuccessor_1)

    def findSuccessor_1(self, n2):
        n2.getSuccessor().addCallbacks(findSuccessor_2, callbackArgs=n2)
        
    def findSuccessor_2(self, address, n2):
        if address: 
            return address
        else:
            return n2.address
    
    def findPredecessor(self, id):
        if self.finger[1] is None:
            return self
        n2 = self
        return self.findPredecessor_1(n2, id)        
    def findPredecessor_1(self, n2, id):
        n2.getSuccessor().addCallback(findPredecessor_2, n2, id)
    def findPredecessor_2(self, n3, n2, id):
        if not betweenR(id, n2.id, n3.id):
            n2.closestPrecedingFinger(id).addCallback(lambda a,  id=id, self=self: self.getNodeAt(a).addCallback(lambda n, id=id, self=self: findPredecessor_1(n, id)))
        else:
            return n2

    def perspective_closestPrecedingFinger(self, id):
        for i in xrange(NBIT, 0, -1):
            if not self.finger[i]: continue
            if between(self.finger[i].id, self.id, id):
                return self.finger[i].address
        return self.address

    def getNodeAt(self, address):
        return pb.connect(address[0], address[1], "chord", "", "chord").addCallback(lambda n: n.getSelf())
        
    def getSelf(self):
        # necessary to produce proper Copyable behaviour
        return self
    
    def stabilise(self):
        """Verify our immediate successor and tell them about us.
        Called periodically."""
        self.finger[1].getPredecessor().addCallback(stabilise_1)

    def stabilise_1(self, p):
        if p != self.address:
            self.perspective_notify(p)

    def fixFingers(self):
        """Refresh a random finger table entry.
        Called periodically."""
        i = random.randrange(1, len(self.finger)+1)
        self.finger[i] = self.findSuccessor(self.start(i))
    
    def perspective_notify(self, addr):        
        """n thinks it might be our predecessor."""
        self.getNodeAt(addr).addCallback(notify)

    def notify(self, n):   
        if (self.pred is self or self.pred is None or 
          between(n.id, self.pred.id, self.id)):
            self.pred = n
            n.notify(self.address, pbanswer=0)
        if self.finger[1] is None or between(n.id, self.id, self.finger[1].id):
            self.finger[1] = n
            n.notify(self.address)
        for i in xrange(2, len(self.finger)):
            if self.finger[i] is None or betweenL(n.id, self.start(i), self.finger[i].id):
                self.finger[i] = n

    def start(self, k):
        assert 1 <= k <= NBIT
        r = (self.id + 2L**(k-1)) % 2L**NBIT
        if r == 0:
            return 2L**NBIT
        else:
            return r
