from twisted.web import spider
from twisted.internet import app
from twisted.python.util import println

a = app.Application("spider")
s = spider.SpiderSender("spider", a)
s.addTargets(['http://twistedmatrix.com/'])
s.maxDepth = 1
s.notifyDownloadStart = lambda uri: println('starting', uri)
s.notifyDownloadEnd = lambda uri: println('stopping', uri)
a.run(save=0)
