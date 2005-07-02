# -*- test-case-name: twisted.web2.test.test_cgi,twisted.web2.test.test_http -*-
# See LICENSE for details.

"""
Various backend channel implementations for web2.
"""
from twisted.web2.channel.cgi import startCGI
from twisted.web2.channel.scgi import SCGIFactory
from twisted.web2.channel.http import HTTPFactory
from twisted.web2.channel.fastcgi import FastCGIFactory

__all__ = ['startCGI', 'SCGIFactory', 'HTTPFactory', 'FastCGIFactory']
