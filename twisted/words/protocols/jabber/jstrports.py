# -*- test-case-name: twisted.words.test -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.


""" A temporary placeholder for client-capable strports, until we
sufficient use cases get identified """

from twisted.internet.endpoints import _parse

def _parseTCPSSL(factory, domain, port):
    """ For the moment, parse TCP or SSL connections the same """
    return (domain, int(port), factory), {}

def _parseUNIX(factory, address):
    return (address, factory), {}


_funcs = { "tcp"  : _parseTCPSSL,
           "unix" : _parseUNIX,
           "ssl"  : _parseTCPSSL }


def parse(description, factory, quoting=False):
    args, kw = _parse(description, quoting)
    return (args[0].upper(),) + _funcs[args[0]](factory, *args[1:], **kw)

def client(description, factory, quoting=False):
    from twisted.application import internet
    name, args, kw = parse(description, factory, quoting)
    return getattr(internet, name + 'Client')(*args, **kw)
