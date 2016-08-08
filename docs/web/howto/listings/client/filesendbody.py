from __future__ import print_function

from StringIO import StringIO

from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from twisted.web.client import FileBodyProducer

agent = Agent(reactor)
body = FileBodyProducer(StringIO("hello, world"))
d = agent.request(
    'GET',
    'http://example.com/',
    Headers({'User-Agent': ['Twisted Web Client Example'],
             'Content-Type': ['text/x-greeting']}),
    body)

def cbResponse(ignored):
    print('Response received')
d.addCallback(cbResponse)

def cbShutdown(ignored):
    reactor.stop()
d.addBoth(cbShutdown)

reactor.run()
