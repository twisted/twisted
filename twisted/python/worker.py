"""
twisted.worker: a single-threaded threadable Dispatcher.

see the 'threadable' module for more information.
"""
import traceback
import sys

class Dispatcher:
    def __init__(self):
        self.q = []
        self.owners = []

    def dispatch(self, owner, func, *args, **kw):
        o = (owner, func, args, kw)
        self.q.append(o)

    dispatchOS = dispatch
    
    def withThisOwned(self, owner, func, *args, **kw):
        self.own(owner)
        try:
            return apply(func,args,kw)
        finally:
            self.disown(owner)
        
    def work(self):
        """
        Do some work (run all the previously registered callbacks).
        Returns whether there remains work to be done.
        """
        if not self.q:
            return 0
        for owner,func,args,kw in self.q:
            self.own(owner)
            try: apply(func, args, kw)
            except:
                traceback.print_exc(file=sys.stdout)
            self.disown(owner)
        self.q = []
        return 1
    
    def own(self, owner):
        if owner is not None:
            self.owners.append(owner)

    def disown(self, owner):
        if owner is not None:
            x = self.owners.pop()
            assert x is owner, "Bad disown"

    def owner(self):
        try:
            return self.owners[-1]
        except:
            return self.defaultOwner

    def stop(self):
        self.work()
