# -*- test-case-name: twisted.words.test.test_jabbererror -*-
#
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
XMPP Error support.
"""


import copy
from typing import Optional

from twisted.python.compat import unicode
from twisted.words.xish import domish

NS_XML = "http://www.w3.org/XML/1998/namespace"
NS_XMPP_STREAMS = "urn:ietf:params:xml:ns:xmpp-streams"
NS_XMPP_STANZAS = "urn:ietf:params:xml:ns:xmpp-stanzas"

STANZA_CONDITIONS = {
    'bad-request':              {'code': '400', 'type': 'modify'},
    'conflict':                 {'code': '409', 'type': 'cancel'},
    'feature-not-implemented':  {'code': '501', 'type': 'cancel'},
    'forbidden':                {'code': '403', 'type': 'auth'},
    'gone':                     {'code': '302', 'type': 'modify'},
    'internal-server-error':    {'code': '500', 'type': 'wait'},
    'item-not-found':           {'code': '404', 'type': 'cancel'},
    'jid-malformed':            {'code': '400', 'type': 'modify'},
    'not-acceptable':           {'code': '406', 'type': 'modify'},
    'not-allowed':              {'code': '405', 'type': 'cancel'},
    'not-authorized':           {'code': '401', 'type': 'auth'},
    'payment-required':         {'code': '402', 'type': 'auth'},
    'recipient-unavailable':    {'code': '404', 'type': 'wait'},
    'redirect':                 {'code': '302', 'type': 'modify'},
    'registration-required':    {'code': '407', 'type': 'auth'},
    'remote-server-not-found':  {'code': '404', 'type': 'cancel'},
    'remote-server-timeout':    {'code': '504', 'type': 'wait'},
    'resource-constraint':      {'code': '500', 'type': 'wait'},
    'service-unavailable':      {'code': '503', 'type': 'cancel'},
    'subscription-required':    {'code': '407', 'type': 'auth'},
    'undefined-condition':      {'code': '500', 'type': None},
    'unexpected-request':       {'code': '400', 'type': 'wait'},
}

CODES_TO_CONDITIONS = {
    '302': ('gone', 'modify'),
    '400': ('bad-request', 'modify'),
    '401': ('not-authorized', 'auth'),
    '402': ('payment-required', 'auth'),
    '403': ('forbidden', 'auth'),
    '404': ('item-not-found', 'cancel'),
    '405': ('not-allowed', 'cancel'),
    '406': ('not-acceptable', 'modify'),
    '407': ('registration-required', 'auth'),
    '408': ('remote-server-timeout', 'wait'),
    '409': ('conflict', 'cancel'),
    '500': ('internal-server-error', 'wait'),
    '501': ('feature-not-implemented', 'cancel'),
    '502': ('service-unavailable', 'wait'),
    '503': ('service-unavailable', 'cancel'),
    '504': ('remote-server-timeout', 'wait'),
    '510': ('service-unavailable', 'cancel'),
}

class BaseError(Exception):
    """
    Base class for XMPP error exceptions.

    @cvar namespace: The namespace of the C{error} element generated by
                     C{getElement}.
    @type namespace: C{str}
    @ivar condition: The error condition. The valid values are defined by
                     subclasses of L{BaseError}.
    @type contition: C{str}
    @ivar text: Optional text message to supplement the condition or application
                specific condition.
    @type text: C{unicode}
    @ivar textLang: Identifier of the language used for the message in C{text}.
                    Values are as described in RFC 3066.
    @type textLang: C{str}
    @ivar appCondition: Application specific condition element, supplementing
                        the error condition in C{condition}.
    @type appCondition: object providing L{domish.IElement}.
    """

    namespace = None  # type: Optional[str]

    def __init__(self, condition, text=None, textLang=None, appCondition=None):
        Exception.__init__(self)
        self.condition = condition
        self.text = text
        self.textLang = textLang
        self.appCondition = appCondition


    def __str__(self):
        message = "%s with condition %r" % (self.__class__.__name__,
                                            self.condition)

        if self.text:
            message += ': ' + self.text

        return message


    def getElement(self):
        """
        Get XML representation from self.

        The method creates an L{domish} representation of the
        error data contained in this exception.

        @rtype: L{domish.Element}
        """
        error = domish.Element((None, 'error'))
        error.addElement((self.namespace, self.condition))
        if self.text:
            text = error.addElement((self.namespace, 'text'),
                                    content=self.text)
            if self.textLang:
                text[(NS_XML, 'lang')] = self.textLang
        if self.appCondition:
            error.addChild(self.appCondition)
        return error



class StreamError(BaseError):
    """
    Stream Error exception.

    Refer to RFC 3920, section 4.7.3, for the allowed values for C{condition}.
    """

    namespace = NS_XMPP_STREAMS

    def getElement(self):
        """
        Get XML representation from self.

        Overrides the base L{BaseError.getElement} to make sure the returned
        element is in the XML Stream namespace.

        @rtype: L{domish.Element}
        """
        from twisted.words.protocols.jabber.xmlstream import NS_STREAMS

        error = BaseError.getElement(self)
        error.uri = NS_STREAMS
        return error



class StanzaError(BaseError):
    """
    Stanza Error exception.

    Refer to RFC 3920, section 9.3, for the allowed values for C{condition} and
    C{type}.

    @ivar type: The stanza error type. Gives a suggestion to the recipient
                of the error on how to proceed.
    @type type: C{str}
    @ivar code: A numeric identifier for the error condition for backwards
                compatibility with pre-XMPP Jabber implementations.
    """

    namespace = NS_XMPP_STANZAS

    def __init__(self, condition, type=None, text=None, textLang=None,
                       appCondition=None):
        BaseError.__init__(self, condition, text, textLang, appCondition)

        if type is None:
            try:
                type = STANZA_CONDITIONS[condition]['type']
            except KeyError:
                pass
        self.type = type

        try:
            self.code = STANZA_CONDITIONS[condition]['code']
        except KeyError:
            self.code = None

        self.children = []
        self.iq = None


    def getElement(self):
        """
        Get XML representation from self.

        Overrides the base L{BaseError.getElement} to make sure the returned
        element has a C{type} attribute and optionally a legacy C{code}
        attribute.

        @rtype: L{domish.Element}
        """
        error = BaseError.getElement(self)
        error['type'] = self.type
        if self.code:
            error['code'] = self.code
        return error


    def toResponse(self, stanza):
        """
        Construct error response stanza.

        The C{stanza} is transformed into an error response stanza by
        swapping the C{to} and C{from} addresses and inserting an error
        element.

        @note: This creates a shallow copy of the list of child elements of the
               stanza. The child elements themselves are not copied themselves,
               and references to their parent element will still point to the
               original stanza element.

               The serialization of an element does not use the reference to
               its parent, so the typical use case of immediately sending out
               the constructed error response is not affected.

        @param stanza: the stanza to respond to
        @type stanza: L{domish.Element}
        """
        from twisted.words.protocols.jabber.xmlstream import toResponse
        response = toResponse(stanza, stanzaType='error')
        response.children = copy.copy(stanza.children)
        response.addChild(self.getElement())
        return response



def _parseError(error, errorNamespace):
    """
    Parses an error element.

    @param error: The error element to be parsed
    @type error: L{domish.Element}
    @param errorNamespace: The namespace of the elements that hold the error
                           condition and text.
    @type errorNamespace: C{str}
    @return: Dictionary with extracted error information. If present, keys
             C{condition}, C{text}, C{textLang} have a string value,
             and C{appCondition} has an L{domish.Element} value.
    @rtype: C{dict}
    """
    condition = None
    text = None
    textLang = None
    appCondition = None

    for element in error.elements():
        if element.uri == errorNamespace:
            if element.name == 'text':
                text = unicode(element)
                textLang = element.getAttribute((NS_XML, 'lang'))
            else:
                condition = element.name
        else:
            appCondition = element

    return {
        'condition': condition,
        'text': text,
        'textLang': textLang,
        'appCondition': appCondition,
    }



def exceptionFromStreamError(element):
    """
    Build an exception object from a stream error.

    @param element: the stream error
    @type element: L{domish.Element}
    @return: the generated exception object
    @rtype: L{StreamError}
    """
    error = _parseError(element, NS_XMPP_STREAMS)

    exception = StreamError(error['condition'],
                            error['text'],
                            error['textLang'],
                            error['appCondition'])

    return exception



def exceptionFromStanza(stanza):
    """
    Build an exception object from an error stanza.

    @param stanza: the error stanza
    @type stanza: L{domish.Element}
    @return: the generated exception object
    @rtype: L{StanzaError}
    """
    children = []
    condition = text = textLang = appCondition = type = code = None

    for element in stanza.elements():
        if element.name == 'error' and element.uri == stanza.uri:
            code = element.getAttribute('code')
            type = element.getAttribute('type')
            error = _parseError(element, NS_XMPP_STANZAS)
            condition = error['condition']
            text = error['text']
            textLang = error['textLang']
            appCondition = error['appCondition']

            if not condition and code:
               condition, type = CODES_TO_CONDITIONS[code]
               text = unicode(stanza.error)
        else:
            children.append(element)

    if condition is None:
        # TODO: raise exception instead?
        return StanzaError(None)

    exception = StanzaError(condition, type, text, textLang, appCondition)

    exception.children = children
    exception.stanza = stanza

    return exception
