#! /usr/bin/python

from twisted.trial import unittest
from twisted.pb import schema

class Dummy:
    pass

HEADER = 64
INTSIZE = HEADER+1
STR10 = HEADER+1+10

class ConformTest(unittest.TestCase):
    """This tests how Constraints are asserted on outbound objects (where the
    object already exists). Inbound constraints are checked in
    test_banana.InboundByteStream in the various testConstrainedFoo methods.
    """
    def conforms(self, c, obj):
        c.checkObject(obj)
    def violates(self, c, obj):
        self.assertRaises(schema.Violation, c.checkObject, obj)
    def assertSize(self, c, maxsize):
        return
        self.assertEquals(c.maxSize(), maxsize)
    def assertDepth(self, c, maxdepth):
        self.assertEquals(c.maxDepth(), maxdepth)
    def assertUnboundedSize(self, c):
        self.assertRaises(schema.UnboundedSchema, c.maxSize)
    def assertUnboundedDepth(self, c):
        self.assertRaises(schema.UnboundedSchema, c.maxDepth)

    def testAny(self):
        c = schema.Constraint()
        self.assertUnboundedSize(c)
        self.assertUnboundedDepth(c)

    def testInteger(self):
        # s_int32_t
        c = schema.IntegerConstraint()
        self.assertSize(c, INTSIZE)
        self.assertDepth(c, 1)
        self.conforms(c, 123)
        self.violates(c, 2**64)
        self.conforms(c, 0)
        self.conforms(c, 2**31-1)
        self.violates(c, 2**31)
        self.conforms(c, -2**31)
        self.violates(c, -2**31-1)
        self.violates(c, "123")
        self.violates(c, Dummy())
        self.violates(c, None)

    def testLargeInteger(self):
        c = schema.IntegerConstraint(64)
        self.assertSize(c, INTSIZE+64)
        self.assertDepth(c, 1)
        self.conforms(c, 123)
        self.violates(c, "123")
        self.violates(c, None)
        self.conforms(c, 2**512-1)
        self.violates(c, 2**512)
        self.conforms(c, -2**512+1)
        self.violates(c, -2**512)

    def testString(self):
        c = schema.StringConstraint(10)
        self.assertSize(c, STR10)
        self.assertSize(c, STR10) # twice to test seen=[] logic
        self.assertDepth(c, 1)
        self.conforms(c, "I'm short")
        self.violates(c, "I am too long")
        self.conforms(c, "a" * 10)
        self.violates(c, "a" * 11)
        self.violates(c, 123)
        self.violates(c, Dummy())
        self.violates(c, None)

    def testBool(self):
        c = schema.BooleanConstraint()
        self.assertSize(c, 147)
        self.assertDepth(c, 2)
        self.conforms(c, False)
        self.conforms(c, True)
        self.violates(c, 0)
        self.violates(c, 1)
        self.violates(c, "vrai")
        self.violates(c, Dummy())
        self.violates(c, None)
        
    def testPoly(self):
        c = schema.PolyConstraint(schema.StringConstraint(100),
                                  schema.IntegerConstraint())
        self.assertSize(c, 165)
        self.assertDepth(c, 1)

    def testTuple(self):
        c = schema.TupleConstraint(schema.StringConstraint(10),
                                   schema.StringConstraint(100),
                                   schema.IntegerConstraint() )
        self.conforms(c, ("hi", "there buddy, you're number", 1))
        self.violates(c, "nope")
        self.violates(c, ("string", "string", "NaN"))
        self.violates(c, ("string that is too long", "string", 1))
        self.violates(c, ["Are tuples", "and lists the same?", 0])
        self.assertSize(c, 72+75+165+73)
        self.assertDepth(c, 2)

    def testNestedTuple(self):
        inner = schema.TupleConstraint(schema.StringConstraint(10),
                                       schema.IntegerConstraint())
        self.assertSize(inner, 72+75+73)
        self.assertDepth(inner, 2)
        outer = schema.TupleConstraint(schema.StringConstraint(100),
                                       inner)
        self.assertSize(outer, 72+165 + 72+75+73)
        self.assertDepth(outer, 3)

        self.conforms(inner, ("hi", 2))
        self.conforms(outer, ("long string here", ("short", 3)))
        self.violates(outer, (("long string here", ("short", 3, "extra"))))
        self.violates(outer, (("long string here", ("too long string", 3))))

        outer2 = schema.TupleConstraint(inner, inner)
        self.assertSize(outer2, 72+ 2*(72+75+73))
        self.assertDepth(outer2, 3)
        self.conforms(outer2, (("hi", 1), ("there", 2)) )
        self.violates(outer2, ("hi", 1, "flat", 2) )

    def testUnbounded(self):
        big = schema.StringConstraint(None)
        self.assertUnboundedSize(big)
        self.assertDepth(big, 1)
        self.conforms(big, "blah blah blah blah blah" * 1024)
        self.violates(big, 123)

        bag = schema.TupleConstraint(schema.IntegerConstraint(),
                                     big)
        self.assertUnboundedSize(bag)
        self.assertDepth(bag, 2)

        polybag = schema.PolyConstraint(schema.IntegerConstraint(),
                                        bag)
        self.assertUnboundedSize(polybag)
        self.assertDepth(polybag, 2)

    def testRecursion(self):
        # we have to fiddle with PolyConstraint's innards
        value = schema.ChoiceOf(schema.StringConstraint(),
                                schema.IntegerConstraint(),
                                # will add 'value' here
                                )
        self.assertSize(value, 1065)
        self.assertDepth(value, 1)
        self.conforms(value, "key")
        self.conforms(value, 123)
        self.violates(value, [])

        mapping = schema.TupleConstraint(schema.StringConstraint(10),
                                         value)
        self.assertSize(mapping, 72+75+1065)
        self.assertDepth(mapping, 2)
        self.conforms(mapping, ("name", "key"))
        self.conforms(mapping, ("name", 123))
        value.alternatives = value.alternatives + (mapping,)
        
        self.assertUnboundedSize(value)
        self.assertUnboundedDepth(value)
        self.assertUnboundedSize(mapping)
        self.assertUnboundedDepth(mapping)

        # but note that the constraint can still be applied
        self.conforms(mapping, ("name", 123))
        self.conforms(mapping, ("name", "key"))
        self.conforms(mapping, ("name", ("key", "value")))
        self.conforms(mapping, ("name", ("key", 123)))
        self.violates(mapping, ("name", ("key", [])))
        l = []
        l.append(l)
        self.violates(mapping, ("name", l))

    def testList(self):
        l = schema.ListOf(schema.StringConstraint(10))
        self.assertSize(l, 71 + 30*75)
        self.assertDepth(l, 2)
        self.conforms(l, ["one", "two", "three"])
        self.violates(l, ("can't", "fool", "me"))
        self.violates(l, ["but", "perspicacity", "is too long"])
        self.conforms(l, ["short", "sweet"])

        l2 = schema.ListOf(schema.StringConstraint(10), 3)
        self.assertSize(l2, 71 + 3*75)
        self.assertDepth(l2, 2)
        self.conforms(l2, ["the number", "shall be", "three"])
        self.violates(l2, ["five", "is", "...", "right", "out"])

    def testDict(self):
        d = schema.DictOf(schema.StringConstraint(10),
                          schema.IntegerConstraint(),
                          maxKeys=4)
        
        self.assertDepth(d, 2)
        self.conforms(d, {"a": 1, "b": 2})
        self.conforms(d, {"foo": 123, "bar": 345, "blah": 456, "yar": 789})
        self.violates(d, None)
        self.violates(d, 12)
        self.violates(d, ["nope"])
        self.violates(d, ("nice", "try"))
        self.violates(d, {1:2, 3:4})
        self.violates(d, {"a": "b"})
        self.violates(d, {"a": 1, "b": 2, "c": 3, "d": 4, "toomuch": 5})

    def testAttrDict(self):
        d = schema.AttributeDictConstraint(('a', int), ('b', str))
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.violates(d, {"a": 1, "b": "string", "c": "is a crowd"})

        d = schema.AttributeDictConstraint(('a', int), ('b', str),
                                           ignoreUnknown=True)
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.conforms(d, {"a": 1, "b": "string", "c": "is a crowd"})

        d = schema.AttributeDictConstraint(attributes={"a": int, "b": str})
        self.conforms(d, {"a": 1, "b": "string"})
        self.violates(d, {"a": 1, "b": 2})
        self.violates(d, {"a": 1, "b": "string", "c": "is a crowd"})


class CreateTest(unittest.TestCase):
    def check(self, obj, expected):
        self.failUnless(isinstance(obj, expected))

    def testMakeConstraint(self):
        make = schema.makeConstraint
        c = make(int)
        self.check(c, schema.IntegerConstraint)
        self.failUnlessEqual(c.maxBytes, -1)

        c = make(str)
        self.check(c, schema.StringConstraint)
        self.failUnlessEqual(c.maxLength, 1000)

        self.check(make(bool), schema.BooleanConstraint)
        self.check(make(float), schema.NumberConstraint)

        self.check(make(schema.NumberConstraint()), schema.NumberConstraint)
        c = make((int, str))
        self.check(c, schema.PolyConstraint)
        self.failUnlessEqual(len(c.alternatives), 2)
        self.check(c.alternatives[0], schema.IntegerConstraint)
        self.check(c.alternatives[1], schema.StringConstraint)

