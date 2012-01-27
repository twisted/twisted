# -*- test-case-name: twisted.web.test.test_flatten -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Context-free flattener/serializer for rendering Python objects, possibly
complex or arbitrarily nested, as strings.

"""

from cStringIO import StringIO
from sys import exc_info
from types import GeneratorType
from traceback import extract_tb
from twisted.internet.defer import Deferred
from twisted.web.error import UnfilledSlot, UnsupportedType, FlattenerError

from twisted.web.iweb import IRenderable
from twisted.web._stan import (
    Tag, slot, voidElements, Comment, CDATA, CharRef)



def escapedData(data, inAttribute):
    """
    Escape a string for inclusion in a document.

    @type data: C{str} or C{unicode}
    @param data: The string to escape.

    @type inAttribute: C{bool}
    @param inAttribute: A flag which, if set, indicates that the string should
        be quoted for use as the value of an XML tag value.

    @rtype: C{str}
    @return: The quoted form of C{data}. If C{data} is unicode, return a utf-8
        encoded string.
    """
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    data = data.replace('&', '&amp;'
        ).replace('<', '&lt;'
        ).replace('>', '&gt;')
    if inAttribute:
        data = data.replace('"', '&quot;')
    return data


def escapedCDATA(data):
    """
    Escape CDATA for inclusion in a document.

    @type data: C{str} or C{unicode}
    @param data: The string to escape.

    @rtype: C{str}
    @return: The quoted form of C{data}. If C{data} is unicode, return a utf-8
        encoded string.
    """
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    return data.replace(']]>', ']]]]><![CDATA[>')


def escapedComment(data):
    """
    Escape a comment for inclusion in a document.

    @type data: C{str} or C{unicode}
    @param data: The string to escape.

    @rtype: C{str}
    @return: The quoted form of C{data}. If C{data} is unicode, return a utf-8
        encoded string.
    """
    if isinstance(data, unicode):
        data = data.encode('utf-8')
    data = data.replace('--', '- - ').replace('>', '&gt;')
    if data and data[-1] == '-':
        data += ' '
    return data


def _getSlotValue(name, slotData, default=None):
    """
    Find the value of the named slot in the given stack of slot data.
    """
    for slotFrame in slotData[::-1]:
        if slotFrame is not None and name in slotFrame:
            return slotFrame[name]
    else:
        if default is not None:
            return default
        raise UnfilledSlot(name)


def _flattenElement(request, root, slotData, renderFactory, inAttribute):
    """
    Make C{root} slightly more flat by yielding all its immediate contents 
    as strings, deferreds or generators that are recursive calls to itself.

    @param request: A request object which will be passed to
        L{IRenderable.render}.

    @param root: An object to be made flatter.  This may be of type C{unicode},
        C{str}, L{slot}, L{Tag}, L{URL}, L{tuple}, L{list}, L{GeneratorType},
        L{Deferred}, or an object that implements L{IRenderable}.

    @param slotData: A C{list} of C{dict} mapping C{str} slot names to data
        with which those slots will be replaced.

    @param renderFactory: If not C{None}, An object that provides L{IRenderable}.

    @param inAttribute: A flag which, if set, indicates that C{str} and
        C{unicode} instances encountered must be quoted as for XML tag
        attribute values.

    @return: An iterator which yields C{str}, L{Deferred}, and more iterators
        of the same type.
    """

    if isinstance(root, (str, unicode)):
        yield escapedData(root, inAttribute)
    elif isinstance(root, slot):
        slotValue = _getSlotValue(root.name, slotData, root.default)
        yield _flattenElement(request, slotValue, slotData, renderFactory,
                inAttribute)
    elif isinstance(root, CDATA):
        yield '<![CDATA['
        yield escapedCDATA(root.data)
        yield ']]>'
    elif isinstance(root, Comment):
        yield '<!--'
        yield escapedComment(root.data)
        yield '-->'
    elif isinstance(root, Tag):
        slotData.append(root.slotData)
        if root.render is not None:
            rendererName = root.render
            rootClone = root.clone(False)
            rootClone.render = None
            renderMethod = renderFactory.lookupRenderMethod(rendererName)
            result = renderMethod(request, rootClone)
            yield _flattenElement(request, result, slotData, renderFactory,
                    False)
            slotData.pop()
            return

        if not root.tagName:
            yield _flattenElement(request, root.children, slotData, renderFactory, False)
            return

        yield '<'
        if isinstance(root.tagName, unicode):
            tagName = root.tagName.encode('ascii')
        else:
            tagName = str(root.tagName)
        yield tagName
        for k, v in root.attributes.iteritems():
            if isinstance(k, unicode):
                k = k.encode('ascii')
            yield ' ' + k + '="'
            yield _flattenElement(request, v, slotData, renderFactory, True)
            yield '"'
        if root.children or tagName not in voidElements:
            yield '>'
            yield _flattenElement(request, root.children, slotData, renderFactory, False)
            yield '</' + tagName + '>'
        else:
            yield ' />'

    elif isinstance(root, (tuple, list, GeneratorType)):
        for element in root:
            yield _flattenElement(request, element, slotData, renderFactory,
                    inAttribute)
    elif isinstance(root, CharRef):
        yield '&#%d;' % (root.ordinal,)
    elif isinstance(root, Deferred):
        yield root.addCallback(
            lambda result: (result, _flattenElement(request, result, slotData,
                                             renderFactory, inAttribute)))
    elif IRenderable.providedBy(root):
        result = root.render(request)
        yield _flattenElement(request, result, slotData, root, inAttribute)
    else:
        raise UnsupportedType(root)


def _flattenTree(request, root):
    """
    Make C{root} into an iterable of C{str} and L{Deferred} by doing a
    depth first traversal of the tree.

    @param request: A request object which will be passed to
        L{IRenderable.render}.

    @param root: An object to be made flatter.  This may be of type C{unicode},
        C{str}, L{slot}, L{Tag}, L{tuple}, L{list}, L{GeneratorType},
        L{Deferred}, or something providing L{IRenderable}.

    @return: An iterator which yields objects of type C{str} and L{Deferred}.
        A L{Deferred} is only yielded when one is encountered in the process of
        flattening C{root}.  The returned iterator must not be iterated again
        until the L{Deferred} is called back.
    """
    stack = [_flattenElement(request, root, [], None, False)]
    while stack:
        try:
            # In Python 2.5, after an exception, a generator's gi_frame is
            # None.
            frame = stack[-1].gi_frame
            element = stack[-1].next()
        except StopIteration:
            stack.pop()
        except Exception, e:
            stack.pop()
            roots = []
            for generator in stack:
                roots.append(generator.gi_frame.f_locals['root'])
            roots.append(frame.f_locals['root'])
            raise FlattenerError(e, roots, extract_tb(exc_info()[2]))
        else:
            if type(element) is str:
                yield element
            elif isinstance(element, Deferred):
                def cbx((original, toFlatten)):
                    stack.append(toFlatten)
                    return original
                yield element.addCallback(cbx)
            else:
                stack.append(element)


def _writeFlattenedData(state, write, result):
    """
    Take strings from an iterator and pass them to a writer function.

    @param state: An iterator of C{str} and L{Deferred}.  C{str} instances will
        be passed to C{write}.  L{Deferred} instances will be waited on before
        resuming iteration of C{state}.

    @param write: A callable which will be invoked with each C{str}
        produced by iterating C{state}.

    @param result: A L{Deferred} which will be called back when C{state} has
        been completely flattened into C{write} or which will be errbacked if
        an exception in a generator passed to C{state} or an errback from a
        L{Deferred} from state occurs.

    @return: C{None}
    """
    while True:
        try:
            element = state.next()
        except StopIteration:
            result.callback(None)
        except:
            result.errback()
        else:
            if type(element) is str:
                write(element)
                continue
            else:
                def cby(original):
                    _writeFlattenedData(state, write, result)
                    return original
                element.addCallbacks(cby, result.errback)
        break


def flatten(request, root, write):
    """
    Incrementally write out a string representation of C{root} using C{write}.

    In order to create a string representation, C{root} will be decomposed into
    simpler objects which will themselves be decomposed and so on until strings
    or objects which can easily be converted to strings are encountered.

    @param request: A request object which will be passed to the C{render}
        method of any L{IRenderable} provider which is encountered.

    @param root: An object to be made flatter.  This may be of type C{unicode},
        C{str}, L{slot}, L{Tag}, L{tuple}, L{list}, L{GeneratorType},
        L{Deferred}, or something that provides L{IRenderable}.

    @param write: A callable which will be invoked with each C{str}
        produced by flattening C{root}.

    @return: A L{Deferred} which will be called back when C{root} has
        been completely flattened into C{write} or which will be errbacked if
        an unexpected exception occurs.
    """
    result = Deferred()
    state = _flattenTree(request, root)
    _writeFlattenedData(state, write, result)
    return result


def flattenString(request, root):
    """
    Collate a string representation of C{root} into a single string.

    This is basically gluing L{flatten} to a C{StringIO} and returning the
    results. See L{flatten} for the exact meanings of C{request} and
    C{root}.

    @return: A L{Deferred} which will be called back with a single string as
        its result when C{root} has been completely flattened into C{write} or
        which will be errbacked if an unexpected exception occurs.
    """
    io = StringIO()
    d = flatten(request, root, io.write)
    d.addCallback(lambda _: io.getvalue())
    return d
