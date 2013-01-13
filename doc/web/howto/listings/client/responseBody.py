from pprint import pformat

from twisted.internet.task import react
from twisted.web.client import Agent, getBody
from twisted.web.http_headers import Headers


def cbRequest(response):
    print 'Response version:', response.version
    print 'Response code:', response.code
    print 'Response phrase:', response.phrase
    print 'Response headers:'
    print pformat(list(response.headers.getAllRawHeaders()))
    d = getBody(response)
    d.addCallback(cbBody)
    return d

def cbBody(body):
    print 'Rsponse body:'
    print body

def main(reactor):
    agent = Agent(reactor)
    d = agent.request(
        'GET',
        'http://example.com/',
        Headers({'User-Agent': ['Twisted Web Client Example']}),
        None)
    d.addCallback(cbRequest)

react(main, ())
