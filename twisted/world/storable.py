# -*- test-case-name: twisted.test.test_world -*-
#
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

import sys
from struct import pack

from twisted.python import reflect
from twisted.python.compat import True, False

from twisted.world import hashless
from twisted.world.util import Backwards


class Ref(object):
    """A forward reference to a class, for __schema__"""
    def __init__(self, name, _back=1):
        self.name = name
        frame = sys._getframe()
        for _ in range(_back):
            frame = frame.f_back
        self.module = frame.f_globals.get('__name__', '')
        self.cls = None

    def __call__(self):
        if self.cls:
            return self.cls
        c = self.cls = reflect.namedClass(str(self))
        return c
    
    def __str__(self):
        if self.module:
            return self.module + '.' + self.name
        else:
            return self.name

class RefCache(object):
    def __init__(self):
        self.classcache = {}

    def refForClass(self, name):
        try:
            return self.classcache[name]
        except KeyError:
            self.classcache[name] = rval = Ref(name, _back=2)
            return rval

ref = RefCache().refForClass


def _upgradeSchema(s):
    d = {}
    for (_type, _name) in s:
        d[_name] = _type
    return d

class MetaStorable(type):
    """
    not entirely clear what this will do (it seems useful), but currently it
    makes the adapter registry work through almost-but-not-quite unwarranted
    use of __metaclass__
    """
    def __new__(klass, subklass, bases, klassdict):
        # Python 2.2.0 bug!  yay!
        if '__module__' not in klassdict:
            klassdict['__module__'] = sys._getframe().f_back.f_globals.get('__name__', __name__)
        if '__setattr__' in klassdict and not '__setattr_is_useful_here__' in klassdict:
            #
            # If you're reading this, you probably tried to make a Storable with
            # __setattr__.  It's a bad idea, so what you really want to use are
            # properties or a proxy class.
            #
            # If you have an extremely good reason to use __setattr__, then set
            # __setattr_is_useful_here__ on your class to suppress this warning. 
            #
            warnings.warn("Using __setattr__ in a Storable class is a horrible idea.", 
                SyntaxWarning)

        # Check to see whether debugging is on or not for the class
        isdebug = klassdict.get('__DEBUG__', False)

        # Inherit schema in default mro order.  Note that schema is immutable now,
        # so this only needs to happen once, and we can do it all up front.
        schemas = [getattr(clazz, '__schema__', {}) for clazz in bases]

        # The default schema has no columns, it is guaranteed to
        # inherit something from Storable if nothing else.
        scma = klassdict.get('__schema__', {})

        # Preserve the original schema, possibly for resolving
        # the Python 2.3 MRO compliance.  Also possibly useful
        # for introspection purposes.
        klassdict['_schema_orig'] = scma

        # [(typ, name), (typ, name)...] schema is deprecated
        if not isinstance(scma, dict):
            warnings.warn('%s.__schema__ should now be a name->type dict' % (subklass,), 
                DeprecationWarning)
            scma = _upgradeSchema(scma)
        schemas.insert(0, scma)

        scma = {}
        [scma.update(_) for _ in Backwards(schemas)]
        klassdict['__schema__'] = scma
        
        # sort keys alphabetically
        scma_store = [k for (k, v) in scma.iteritems() if v]
        scma_store.sort()
        scma_store = tuple(scma_store)

        # the storeorder is an immutable list
        klassdict['_schema_storeorder'] = scma_store

        # the loadmap is a mapping of column name -> column index
        # essentially just enumeration of storeorder
        klassdict['_schema_loadmap'] = dict(zip(scma_store, range(len(scma_store))))
        klassdict['__name__'] = subklass
        for sname, stype in scma.items():
            assert sname not in klassdict, "class attribute %s cannot be in __schema__" % (sname,)
            if stype is None:
                if isdebug:
                    # Hooks for "in-memory slots" when debugging Storable subclasses
                    def getter(self, sname=sname+'_'):
                        return object.__getattribute__(self, sname)
                    def setter(self, v, sname=sname+'_'):
                        return object.__setattr__(self, sname, v)
                    getter.func_doc = """get ephemeral attribute %s""" % sname
                    setter.func_doc = """set ephemeral attribute %s""" % sname
                    klassdict[sname] = property(getter, setter, doc='ephemeral(%s)' % (sname,))
                    klassdict[sname + '_'] = None
                else:
                    klassdict[sname] = None
            else:
                # Hooks for "serializable slots" in the schema
                def getter(self, sname=sname):
                    if sname in self._attrcache:
                        return self._attrcache[sname]
                    self._attrcache[sname] = v = self._loadattr(sname)
                    return v
                def setter(self, v, sname=sname):
                    #if sname in self._attrcache and self._attrcache[sname] == v:
                    #    return
                    self._saveattr(sname, v)
                    
                getter.func_doc = """get %s from cache or database""" % sname
                setter.func_doc = """update %s in cache and database""" % sname
                if isinstance(stype, Ref):
                    clsname = str(stype)
                elif isinstance(stype, type):
                    clsname = stype.__name__
                else:
                    clsname = repr(stype)
                klassdict[sname] = property(getter, setter, doc='%s(%s)' % (clsname, sname))
        if isdebug:
            # lock down attribute setting while debugging Storable subclasses
            def __setattr__(self, attr, value):
                if attr not in dir(self):
                    raise AttributeError(attr)
                object.__setattr__(self, attr, value)
            klassdict['__setattr__'] = __setattr__
        return type.__new__(klass, subklass, bases, klassdict)

# components.registerAdapter(ObjectTypeMapper, MetaStorable, ITypeMapper)

_stayAliveValues = hashless.HashlessWeakValueDictionary()

class Storable:
    __schema__ = {
        '_inmem_fromdb': None,
        '_schema_table': None,
        '_inmem_oid': None,
        '_inmem_genhash': None,
        '_attrcache': None,
        '_schema_oid': int,
        '_schema_genhash': int,
    }

    # Okay, that attribute bears a little explaining.
    
    # The "None"s there are attributes that are present in the actual object's
    # dictionary when it's just sitting around in RAM.  These duplicate the
    # (int, "_schema_xxx")'s for a good reason, so don't remove them.

    # The int attributes are present in both the database and RAM because we
    # need _something_ in RAM to actually tell us where the object is in the
    # database.  It's easier to make the in-memory attributes the OID rather
    # than the offset into the instanceData because this will prevent us from being
    # bitten by reference-corruption errors if there is a problem with the
    # identity cache in the Database instance.  
    
    # <fixed>
    # For example, classes that
    # define __hash__ will currently screw it up because I need to reimplement
    # WeakValueDictionary to use a different hashing strategy but the same key
    # deletion semantics.  That particular bug will be fixed very soon, but
    # hashing and reference identity are dark corners of python that are easy
    # to do subtle things wrong with, and if we mess up in the future, it's
    # important to have a way to _know_ we messed up.
    # </fixed>
    # NOTE: He actually meant Weak*Key*Dictionary

    # These attributes are present in the database for a similar reason: we
    # want sanity checking to make sure the class instanceDatas are in sync with
    # the root "objects" directory.  This will be far less important once we've
    # agressively unit-tested this code (and transaction support).

    __metaclass__ = MetaStorable

    def __new__(klazz, *args, **kwargs):
        self = object.__new__(klazz, *args, **kwargs)
        self._attrcache = {}
        return self
    
    def keepAlive(self, volatileObject):
        """Keep me alive until nobody references volatileObject any more.
        """
        _stayAliveValues[self] = volatileObject

    def fromDB(klass, table, oid, genhash):
        assert klass.__new__ is Storable.__new__, (
            "How'd you do that? %s != %s" % (klass.__new__, Storable.__new__))
        stor = klass.__new__(klass)
        assert len(stor._attrcache) == 0
        stor._inmem_oid = oid
        stor._inmem_genhash = genhash
        stor._inmem_fromdb = True
        stor._schema_table = table
        return stor

    fromDB = classmethod(fromDB)

    def storedUIDPath(self):
        if self._inmem_oid is None and self._inmem_genhash is None:
            return '<<in-memory>>'
        return pack("!ii", self._inmem_oid, self._inmem_genhash).encode("hex")

    def __repr__(self):
        if self._schema_table is None:
            stored = 'not stored'
        else:
            stored = 'stored @ %s' % self._inmem_oid
        return '<Storable %s (%s)>' % (
            reflect.qual(self.__class__), stored)

    def getDatabase(self):
        """Get the database that this object is a member of.
        """
        if self._schema_table is None:
            return None
        return self._schema_table.db
    
    def __awake__(self):
        """ POSSIBLY: a method for when objects 'wake up'
        """

    def __getAttrMapper(self, name):
        # XXX: HACK HACK - reimplement this, it's going to slow things down a lot
        for highType, highName in self._schema_table.getSchema():
            if name == highName:
                if isinstance(highType, Ref):
                    return highType()
                return highType
        else:
            raise AttributeError(name)

    def _saveattr(self, attr, val):
        if self._schema_table is None:
            self._attrcache[attr] = val
            return
        if attr in self._attrcache:
            del self._attrcache[attr]
        #if self.__getAttrMapper(attr).original is None:
        #    pass
        #else:
        #"""
        self._schema_table.setDataFor(self, attr, val)

    def _loadattr(self, attr):
        if self._schema_table is not None:
            mapper = self.__getAttrMapper(attr)
            #if mapper.original is None:
            #    raise AttributeError(attr)
            #else:
            return mapper.highDataFromRow(
                self._schema_table.db.oidsFile.getAt(self._inmem_oid, "offset"),
                attr,
                self._schema_table.db,
                self._schema_table.instanceData)
        
        raise AttributeError("%s (Storable) has not yet set attribute %r" % (self.__name__, attr))

    def _clearcache(self):
        self._attrcache.clear()

