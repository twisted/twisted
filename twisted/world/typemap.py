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


from types import NoneType, ClassType
import struct

from twisted.python import components, reflect
from twisted.world import structfile
from twisted.python.compat import True, False, bool

class ITypeMapper(components.Interface):
    """
    I map between high-level (possibly variable length) python types and
    low-level (guaranteed fixed length) attributes and allow objects to be
    stored in a fixed-length record store.
    """

    def getLowColumns(self, name):
        """
        Get a list of primitive columns that will store all necessary data for
        an object of the type I proxy for.  This is a tuple of (type, name)
        columns.  Low level types are: int, float, long, bool.
        """

    def lowToHigh(self, db, tup):
        """
        Convert a `primitive' tuple to a high-level object with behavior.
        """

    def highToLow(self, db, obj):
        """
        Convert a high-level object to a tuple of low-level objects, to be stored in 
        """


    def getPhysicalSize(self):
        """Return an integer - the size of one column of this datatype.
        """

    def toTuple(self):
        """Convert this typemapper to a tuple which both globally identifies it
        and provides a simple serialization for it.  """

    def null(self):
        """Return a 'null' object that will fit into this column, such as None,
        0, '', etc.
        """


class AbstractTypeMapper(components.Adapter):
    __implements__ = ITypeMapper
    def highDataFromRow(self, index, name, db, sFile):
        dataList = []
        for lowType, lowName in self.getLowColumns(name):
            dataList.append(sFile.getAt(index, lowName))
        return self.lowToHigh(db, dataList)

    def lowDataToRow(self, index, name, db, sFile, value):
        namesAndValues = zip(self.getLowColumns(name),
                             self.highToLow(db, value))
        for (lowType, lowName), lowValue in namesAndValues:
            sFile.setAt(index, lowName, lowValue)


class NoneTypeMapper(AbstractTypeMapper):
    """This shouldn't really get used..."""
    
    def getLowColumns(self, name):
        return []

    def lowToHigh(self, db, tup):
        return None

    def highToLow(self, db, obj):
        return ()

    def getPhysicalSize(self):
        return 0

    def toTuple(self):
        return ('None',)

    def null(self):
        return None

components.registerAdapter(NoneTypeMapper, NoneType, ITypeMapper)

class TypeTypeMapper(AbstractTypeMapper):
    def getPhysicalSize(self):
        return struct.calcsize(
            '!' + structfile.StructuredFile.typeToFormatChar[self.original])

    def getLowColumns(self, name):
        return [(self.original, name)]

    def lowToHigh(self, db, tup):
        return self.original(*tup)

    def highToLow(self, db, obj):
        return (self.original(obj),)

    def toTuple(self):
        return (self.original.__name__,)

    def null(self):
        if self.original is int:
            return 0
        elif self.original is float:
            return 0.0
        elif self.original is bool:
            return False

# components.registerAdapter(TypeTypeMapper, type, ITypeMapper)

class Varchar(AbstractTypeMapper):
    # self.original is actually an int
    def getLowColumns(self, name):
        # order is important!
        return (
                (int, name+'$extoid'),
                (int, name+'$extgenhash'),
                (int, name+'$length'),
                (FixedSizeString(self.original), name+'$data'),
                )

    def getPhysicalSize(self):
        INT_SIZE = 4
        return (3 * INT_SIZE) + self.original

    def toTuple(self):
        return ('varchar',self.original)

    def lowToHigh(self, db, tup):
        extoid, extgenhash, length, data = tup
        if extoid:
            strStor = db.retrieveOID(extoid, extgenhash)
            return strStor.getData()
        elif length != -1:
            return data[:length]
        else:
            return None

    def highToLow(self, db, obj):
        if obj is None:
            oid = 0
            genhash = 0
            data = '\x00' * self.original
            length = -1
        elif len(obj) > self.original:
            oid, genhash = db._insert(StringStore(db, obj), False)
            data = '\x00' * self.original
            length = 0
        else:
            oid, genhash = 0, 0
            data = obj
            length = len(obj)
        return oid, genhash, length, data

    def null(self):
        return ''

class TupleTypeMapper(AbstractTypeMapper):
    def getPhysicalSize(self):
        i = 0
        for t in self.original:
            i += getMapper(t).getPhysicalSize()
        return i

    def getLowColumns(self, name):
        x = []
        i = 0
        for t in self.original:
            x.extend(getMapper(t).getLowColumns("%s$%s" % (name, i)))
            i += 1
        return tuple(x)

    def toTuple(self):
        l = ['tuple']
        for t in self.original:
            l.append(getMapper(t).toTuple())
        return tuple(l)

    def lowToHigh(self, db, tup):
        offt = 0
        x = []
        for t in self.original:
            tm = getMapper(t)
            lcol = len(tm.getLowColumns(""))
            subtup = tup[offt:offt+lcol]
            offt += lcol
            x.append(tm.lowToHigh(db, subtup))
        return tuple(x)

    def highToLow(self, db, obj):
        x = []
        assert len(self.original) == len(obj)
        for t, o in zip(self.original, obj):
            x.extend(getMapper(t).highToLow(db,o))
        return tuple(x)

    def null(self):
        nl = []
        for t in self.original:
            nl.append(getMapper(t).null())
        return tuple(nl)

_db_nil = (0, 0)

class ObjectTypeMapper(AbstractTypeMapper):
    def getLowColumns(self, name):
        return (
                (int, name+"$oid"), 
                (int, name+"$hash"),
                )

    def toTuple(self):
        return ('object', reflect.qual(self.original))

    def getPhysicalSize(self):
        INT_SIZE = 4
        return 2 * INT_SIZE
    
    def lowDataToRow(self, index, name, db, sFile, value):
        retval = AbstractTypeMapper.lowDataToRow(self, index, name, db, sFile, value)
        # XXX I *think* all incref/decref can be bottlenecked through here;
        # whenever we load or save an OID we can tell the database.  There is
        # currently only one other caller of highToLow and that's of dubious
        # utility; perhaps these should be merged?
        return retval

    def lowToHigh(self, db, tup):
        if tup == _db_nil:
            return None
        oid, genhash = tup
        return db.retrieveOID(oid, genhash)

    def highToLow(self, db, obj):
        if obj is None:
            return _db_nil
        assert isinstance(obj, Storable), "%s not Storable" % obj
        oid, genhash = db._insert(obj, False)
        return oid, genhash

    def null(self):
        return None


class StorableListTypeMapper(ObjectTypeMapper):
    def __init__(self, original):
        from twisted.world.compound import StorableList
        ObjectTypeMapper.__init__(self, StorableList)
        # Can't do this here because of "ref"
        # ltype = getMapper(original)
        # self.ltype = ltype
        self.lclass = original

    def getType(self):
        return getMapper(self.lclass)

    def toTuple(self):
        return ('list', self.getType().toTuple())

    def highToLow(self, db, obj):
        if isinstance(obj, list):
            from twisted.world.compound import StorableList
            st = StorableList(db, self.getType())
            d = {}
            d[st] = 1
            assert st in d
            assert st in db.identityToUID
            for x in obj:
                st.append(x)
            assert st in d
            assert st in db.identityToUID
            return ObjectTypeMapper.highToLow(self, db, st)
        else:
            return ObjectTypeMapper.highToLow(self, db, obj)

class StorableDictionaryTypeMapper(ObjectTypeMapper):
    def __init__(self, keyClass, valueClass):
        from twisted.world.compound import StorableDictionaryStore
        self.keyClass = keyClass
        self.valueClass = valueClass

    def getKeyType(self):
        return getMapper(self.keyClass)
    
    def getValueType(self):
        return getMapper(self.valueClass)

    def lowToHigh(self, db, tup):
        o = ObjectTypeMapper.lowToHigh(self,db,tup)
        from twisted.world.compound import StorableDictionaryFacade
        return StorableDictionaryFacade(o)

    def highToLow(self, db, obj):
        from twisted.world.compound import StorableDictionaryFacade, StorableDictionaryStore
        if isinstance(obj, dict):
            newstor = StorableDictionaryStore(db, self.getKeyType(), self.getValueType())
            StorableDictionaryFacade(newstor).update(obj)
            return self.highToLow(db, newstor)
        elif isinstance(obj, StorableDictionaryFacade):
            return self.highToLow(db, obj.original)
        elif isinstance(obj, StorableDictionaryStore):
            return ObjectTypeMapper.highToLow(self, db, obj)
        else:
            # XXX TODO: while the lower-level database supports a "slot for
            # anything", the list/dict typemappers sorta breaks that for lists
            # & dictionaries.  On the one hand, using typemappers really
            # constrains the surprisin behavior of setattr/setitem to the one
            # place where you declare it to be explicitly surprising
            # (twisted.world will not create copies o objects unless they are
            # specificially being put into an "OK to copy dicts here" or "OK to
            # copy lists here" slot).  On the other hand, this is really
            # inconvenient if you want to create a "bag" data structure.  maybe
            # we need a "really totally ambivalent" slot that will happily
            # create monstrously inefficient ints/lists/dicts/strings depending
            # on what's put into it?
            raise AttributeError("You're putting something that looks nothing "
                                 "at all like a dict (%s) into a slot that can "
                                 "only hold dicts." % repr(obj))


class TypeMapperMapper(AbstractTypeMapper):
    def __init__(self):
        pass

    def getLowColumns(self, name):
        return [(int,name)]

    def getPhysicalSize(self):
        return 4

    def toTuple(self):
        return ('typemapper',)

    def highToLow(self, db, obj):
        return db.mapperToKey(obj),

    def lowToHigh(self, db, tup):
        return db.keyToMapper(tup[0])

    def null(self):
        return NoneTypeMapper()

class TypeMapperRegistry:
    def __init__(self, d):
        self._mapperCache = d

    def getMapper(self, x):
        if components.implements(x, ITypeMapper):
            if isinstance(x, (ClassType, type)):
                return x()
            return x
        if isinstance(x, ref):
            x = x()
        if x in self._mapperCache:
            return self._mapperCache[x]
        else:
            if isinstance(x, tuple):
                ot = TupleTypeMapper(x)
            elif issubclass(x, Storable):
                ot = ObjectTypeMapper(x)
            else:
                raise NotImplementedError("You can't store that.")
            self._mapperCache[x] = ot
            return ot
        
_defaultMapper = TypeMapperRegistry({
    int: TypeTypeMapper(int),
    str: Varchar(128),
    float: TypeTypeMapper(float),
    bool: TypeTypeMapper(bool),
    None: NoneTypeMapper(None),
    })


getMapper = _defaultMapper.getMapper

from twisted.world.storable import ref, Storable
from twisted.world.structfile import FixedSizeString
from twisted.world.allocator import StringStore
