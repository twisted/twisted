
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest
from twisted.protocols import dict

paramString = "\"This is a dqstring \\w\\i\\t\\h boring stuff like: \\\"\" and t\\hes\\\"e are a\\to\\ms"
goodparams = ["This is a dqstring with boring stuff like: \"", "and", "thes\"e", "are", "atoms"]

class ParamTest(unittest.TestCase):
    def testParseParam(self):
        """Testing command response handling"""
        params = []
        rest = paramString
        while 1:
            (param, rest) = dict.parseParam(rest)
            if param == None:
                break
            params.append(param)
        self.failUnlessEqual(params, goodparams)#, "DictClient.parseParam returns unexpected results")
