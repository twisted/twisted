from twisted.web import spider
from twisted.internet import app

def start(uri):
    print "starting", uri
def stop(uri):
    print "stopping", uri

a = app.Application("spider")
s = spider.SpiderSender("spider", a)
s.addTargets(['http://twistedmatrix.com/'])
s.maxDepth = 1
s.notifyDownloadStart = start
s.notifyDownloadEnd = stop
a.run(save=0)
