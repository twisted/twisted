#!/usr/bin/env python
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

from __future__ import print_function

if __name__ == "__main__":
    from sys import argv
    from twisted.internet.task import react
    from request import main
    raise SystemExit(react(main, argv[1:]))

from twisted.web.iweb import UNKNOWN_LENGTH
from twisted.web.client import Agent
from twisted.web.http_headers import Headers

def display(response):
    print("Response code:", response.code)
    length = response.length
    if length is UNKNOWN_LENGTH:
        length = "(unknown)"
    print("Response length:", length)

def main(reactor, url=b"http://twistedmatrix.com/"):
    agent = Agent(reactor)
    d = agent.request(
        b"GET", url,
        Headers({b'User-Agent': [b'Twisted Web Client Example']}))
    d.addCallback(display)
    return d
