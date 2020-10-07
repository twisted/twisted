from __future__ import print_function

from twisted.internet import reactor
from twisted.python import log, compat
from twisted.web.client import Agent, CookieAgent

def displayCookies(response, cookieJar):
    print('Received response')
    print(response)
    print('Cookies:', len(cookieJar))
    for cookie in cookieJar:
        print(cookie)

def main():
    cookieJar = compat.cookielib.CookieJar()
    agent = CookieAgent(Agent(reactor), cookieJar)

    d = agent.request(b'GET', b'http://httpbin.org/cookies/set?some=data')
    d.addCallback(displayCookies, cookieJar)
    d.addErrback(log.err)
    d.addCallback(lambda ignored: reactor.stop())
    reactor.run()

if __name__ == "__main__":
    main()
