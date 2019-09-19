from __future__ import print_function

from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

from bytesprod import BytesProducer

agent = Agent(reactor)
body = BytesProducer(b"hello, world")
d = agent.request(
    b'POST',
    b'http://httpbin.org/post',
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
