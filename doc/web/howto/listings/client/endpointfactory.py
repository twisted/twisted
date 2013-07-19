from __future__ import print_function

from sys import argv

from twisted.internet.endpoints import TCP4ClientEndpoint, SSL4ClientEndpoint
from twisted.internet.task import react
from twisted.web.client import Agent
from twisted.web.http_headers import Headers


def cbRequest(response):
    print('Response received')

def endpointFactory(reactor, contextFactory, bindAddress, connectTimeout,
                    scheme, host, port):
    print('Creating an endpoint:', reactor, contextFactory, bindAddress,
          connectTimeout, scheme, host, port)
    kwargs = {'bindAddress': bindAddress}
    if connectTimeout is not None:
        kwargs['timeout'] = connectTimeout
    if scheme == 'http':
        return TCP4ClientEndpoint(reactor, host, port, **kwargs)
    elif scheme == 'https':
        return SSL4ClientEndpoint(
            reactor, host, port, contextFactory, **kwargs)
    else:
        raise ValueError("Unsupported scheme: %r" % (scheme,))


def main(reactor, url=b"http://example.com/"):
    agent = Agent(reactor, endpointFactory=endpointFactory)
    d = agent.request(
        'GET', url,
        Headers({'User-Agent': ['Twisted Web Client Example']}),
        None)
    d.addCallback(cbRequest)
    return d

react(main, argv[1:])
