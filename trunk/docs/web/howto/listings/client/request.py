from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

agent = Agent(reactor)

d = agent.request(
    'GET',
    'http://example.com/',
    Headers({'User-Agent': ['Twisted Web Client Example']}),
    None)

def cbResponse(ignored):
    print 'Response received'
d.addCallback(cbResponse)

def cbShutdown(ignored):
    reactor.stop()
d.addBoth(cbShutdown)

reactor.run()
