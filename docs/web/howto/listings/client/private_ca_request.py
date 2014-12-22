#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

if __name__ == "__main__":
    from sys import argv
    from twisted.internet.task import react
    from private_ca_request import main
    raise SystemExit(react(main, argv[1:]))

from twisted.python.filepath import FilePath
from twisted.internet.ssl import Certificate
from twisted.web.iweb import UNKNOWN_LENGTH
from twisted.web.client import BrowserLikePolicyForHTTPS, Agent
from twisted.web.http_headers import Headers

def display(response):
    print("Response code:", response.code)
    length = response.length
    if length is UNKNOWN_LENGTH:
        length = "(unknown)"
    print("Response length:", length)

def main(reactor, ca, url):
    caCertificate = Certificate.loadPEM(FilePath(ca).getContent())
    policy = BrowserLikePolicyForHTTPS(caCertificate)
    agent = Agent(reactor, policy)
    print('Requesting', url, 'with ca', ca)
    d = agent.request(
        b"GET", url,
        Headers({b'User-Agent': [b'Twisted Web Client Example']}))
    d.addCallback(display)
    return d
