# Twisted, the Framework of Your Internet
# Copyright (C) 2001-2002 Matthew W. Lefkowitz
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
#

"""
Persistent Object Partitioning Strategy Involving Concurrent Lightweight Events

POPSICLE is designed to persist objects as close to transparently as possible.
While complete transparency is impossible with python's semantics, popsicle
strives to preserve three things:

    1. preserve a modicum of referential transparency by using Deferreds for
    all references which can not (or should not!) be immediately resolved

    2. allow for the use of multiple persistence strategies with the same
    object.  Specific back-ends we wish to target: filesystem databases, BSDDB,
    ReiserFS, ZODB, and arbitrary RDBMS schemas.

    3. minimize memory usage by paging unnecessary objects out whenever
    possible, transparently to everything involved.  We want to use Python's
    normal garbage collection mechanisms to accomplish this.


There is a top level persistence manager (the 'freezer') which keeps a weak key
dictionary of {persistent_object: [PersistentReference, [savers]]}

The persistent_object should be 'trained' to expect callable objects that
return Deferreds to populate part of it.  Whenever a persistence mechanism
encounters an ID for a different object that could be loaded...

Each Storage is responsible for its own cache management wrt IDs.

Objects that are dirty should call popsicle.dirty(self) to be added to the
dirty list.  when popsicle.clean() is called, the dirty list will be walked,
notifying all savers for each dirty object.

"""
