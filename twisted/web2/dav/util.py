# -*- test-case-name: twisted.web2.test.test_util -*-
##
# Copyright (c) 2005 Apple Computer, Inc. All rights reserved.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# DRI: Wilfredo Sanchez, wsanchez@apple.com
##

"""
Utilities

This API is considered private to static.py and is therefore subject to
change.
"""

__all__ = [
    "allDataFromStream",
    "davXMLFromStream",
    "noDataFromStream",
    "normalizeURL",
    "joinURL",
    "parentForURL",
    "bindMethods",
]

import urllib
from urlparse import urlsplit, urlunsplit
import posixpath # Careful; this module is not documented as public API

from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet.defer import succeed
from twisted.web2.stream import readStream

from twisted.web2.dav import davxml

##
# Reading request body
##

def allDataFromStream(stream, filter=None):
    data = []
    def gotAllData(_):
        if not data: return None
        result = "".join([str(x) for x in data])
        if filter is None:
            return result
        else:
            return filter(result)
    return readStream(stream, data.append).addCallback(gotAllData)

def davXMLFromStream(stream):
    # FIXME:
    #   This reads the request body into a string and then parses it.
    #   A better solution would parse directly and incrementally from the
    #   request stream.
    if stream is None:
        return succeed(None)

    def parse(xml):
        try:
            return davxml.WebDAVDocument.fromString(xml)
        except ValueError:
            log.err("Bad XML:\n%s" % (xml,))
            raise
    return allDataFromStream(stream, parse)

def noDataFromStream(stream):
    def gotData(data):
        if data: raise ValueError("Stream contains unexpected data.")
    return readStream(stream, gotData)

##
# URLs
##

def normalizeURL(url):
    """
    Normalized a URL.
    @param url: a URL.
    @return: the normalized representation of C{url}.  The returned URL will
        never contain a trailing C{"/"}; it is up to the caller to determine
        whether the resource referred to by the URL is a collection and add a
        trailing C{"/"} if so.
    """
    def cleanup(path):
        # For some silly reason, posixpath.normpath doesn't clean up '//' at the
        # start of a filename, so let's clean it up here.
        if path[0] == "/":
            count = 0
            for char in path:
                if char != "/": break
                count += 1
            path = path[count-1:]

        return path

    (scheme, host, path, query, fragment) = urlsplit(cleanup(url))

    path = cleanup(posixpath.normpath(urllib.unquote(path)))

    return urlunsplit((scheme, host, urllib.quote(path), query, fragment))

def joinURL(*urls):
    """
    Appends URLs in series.
    @param urls: URLs to join.
    @return: the normalized URL formed by combining each URL in C{urls}.  The
        returned URL will contain a trailing C{"/"} if and only if the last
        given URL contains a trailing C{"/"}.
    """
    if len(urls) > 0 and len(urls[-1]) > 0 and urls[-1][-1] == "/":
        trailing = "/"
    else:
        trailing = ""

    url = normalizeURL("/".join([url for url in urls]))
    if url == "/":
        return "/"
    else:
        return url + trailing

def parentForURL(url):
    """
    Extracts the URL of the containing collection resource for the resource
    corresponding to a given URL.
    @param url: an absolute (server-relative is OK) URL.
    @return: the normalized URL of the collection resource containing the
        resource corresponding to C{url}.  The returned URL will always contain
        a trailing C{"/"}.
    """
    (scheme, host, path, query, fragment) = urlsplit(normalizeURL(url))

    index = path.rfind("/")
    if index is 0:
        if path == "/":
            return None
        else:
            path = "/"
    else:
        if index is -1:
            raise ValueError("Invalid URL: %s" % (url,))
        else:
            path = path[:index] + "/"

    return urlunsplit((scheme, host, path, query, fragment))

##
# Python magic
##

def unimplemented(obj):
    """
    Throw an exception signifying that the current method is unimplemented
    and should not have been invoked.
    """
    import inspect
    caller = inspect.getouterframes(inspect.currentframe())[1][3]
    raise NotImplementedError("Method %s is unimplemented in subclass %s" % (caller, obj.__class__))

def bindMethods(module, clazz, prefixes=("preconditions_", "http_", "report_")):
    """
    Binds all functions in the given module (as defined by that module's
    C{__all__} attribute) which start with any of the given prefixes as methods
    of the given class.
    @param module: the module in which to search for functions.
    @param clazz: the class to bind found functions to as methods.
    @param prefixes: a sequence of prefixes to match found functions against.
    """
    for submodule_name in module.__all__:
        try:
            __import__(module.__name__ + "." + submodule_name)
        except ImportError:
            log.err("Unable to import module %s" % (module.__name__ + "." + submodule_name,))
            Failure().raiseException()
        submodule = getattr(module, submodule_name)
        for method_name in submodule.__all__:
            for prefix in prefixes:
                if method_name.startswith(prefix):
                    method = getattr(submodule, method_name)
                    setattr(clazz, method_name, method)
                    break
