
# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

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
