
from pyunit import unittest
from twisted.persisted import mailsicle, popsicle

class Dummy:
    __implements__ = mailsicle.IHeaderSaver

    def __init__(self,name):
        self.name = name

    def __repr__(self):
        return '<dummy %r %r>' % (self.name, id(self))

    def setName(self,name):
        self.name = name
        popsicle.dirty(self)

    def getContinuations(self):
        return []

    def getItems(self):
        return [("Name",self.name)]

    def descriptiveName(self):
        return "Dummy %s" % self.name

    def getIndexes(self):
        return [('person-name',self.name)]

    def loadItems(self,items):
        self.name = items[2][1]

    def loadContinuations(self, cont):
        pass


from twisted.python import log
import os
import shutil
class MailsicleTest(unittest.TestCase):
    def testIndexing(self):
        if os.path.exists("BOBJANE_TEST"):
            shutil.rmtree("BOBJANE_TEST")
        ms = mailsicle.Mailsicle("BOBJANE_TEST")
        d1 = Dummy("bob")
        d2 = Dummy("jane")
        popsicle.register(d1, ms)
        popsicle.register(d2, ms)
        popsicle.clean()
        del d1
        del d2
        yy = []
        zz = []
        yy = ms.queryIndex("person-name","bob").fetchNow()
        zz = ms.queryIndex("person-name","bob").fetchNow()
        yy.sort()
        zz.sort()
        # log.err(yy[0])
        self.assertEquals(yy,zz)
        self.assertEquals(len(yy),1)
        yy[0].setName("joe")
        zz = []
        yy = []
        print 'cleaning pops'
        print popsicle.theFreezer.persistentObjects.items()
        popsicle.clean()
        print 'cleaned'
        ms.queryIndex("person-name","bob").fetch().addCallback(yy.extend)
        ms.queryIndex("person-name","joe").fetch().addCallback(zz.extend)
        self.assertEquals(yy,[])
        self.assertEquals(len(zz),1)
