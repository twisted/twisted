from twisted.trial import unittest
from twisted.application import app, service

class TestAppSupport(unittest.TestCase):

    def testSaveApplication(self):
        a = service.Application("hello")
        for style in 'pickle xml source'.split():
            app.saveApplication(a, style, 0, 'helloapplication')
            a1 = app.loadPersisted('helloapplication', style, None)
            self.assertEqual(service.IService(a1).name, "hello")
            app.saveApplication(a, style, 0, None)
            a1 = app.loadPersisted('hello.ta'+style[0], style, None)
            self.assertEqual(service.IService(a1).name, "hello")
        open("hello.tac", 'w').write("""
from twisted.application import service
application = service.Application("hello")
""")
        a1 = app.loadPersisted('hello.tac', 'python', None)
        self.assertEqual(service.IService(a1).name, "hello")
        
    def testTypeGuesser(self):
        self.assertRaises(KeyError, app.guessType, "file.blah")
        self.assertEqual('python', app.guessType("file.py"))
        self.assertEqual('python', app.guessType("file.tac"))
        self.assertEqual('python', app.guessType("file.etac"))
        self.assertEqual('pickle', app.guessType("file.tap"))
        self.assertEqual('pickle', app.guessType("file.etap"))
        self.assertEqual('source', app.guessType("file.tas"))
        self.assertEqual('source', app.guessType("file.etas"))
        self.assertEqual('xml', app.guessType("file.tax"))
        self.assertEqual('xml', app.guessType("file.etax"))

    def testPassphrase(self):
        self.assertEqual(app.getPassphrase(0), None)

    def testLoadApplication(self):
        a = service.Application("hello")
        baseconfig = {'file': None, 'xml': None, 'source': None, 'python':None}
        for style in 'source xml pickle'.split():
            config = baseconfig.copy()
            config[{'pickle': 'file'}.get(style, style)] = 'helloapplication'
            app.saveApplication(a, style, 0, 'helloapplication')
            a1 = app.loadApplication(config, None)
            self.assertEqual(service.IService(a1).name, "hello")
        config = baseconfig.copy()
        config['python'] = 'helloapplication'
        open("helloapplication", 'w').write("""
from twisted.application import service
application = service.Application("hello")
""")
        a1 = app.loadApplication(config, None)
        self.assertEqual(service.IService(a1).name, "hello")
            

'''
def loadApplication(config, passphrase):
def installReactor(reactor):
def runReactor(config, oldstdout, oldstderr):
def runReactorWithLogging(config, oldstdout, oldstderr):
def getPassphrase(needed):
def getApplication(config, passphrase):
def reportProfile(report_profile, name):
def run(runApp, ServerOptions):
def initialLog():
def scheduleSave(app):
def saveApplication(p, type, enc, filename):
def loadPersisted(filename, kind, passphrase):
'''
