# -*- test-case-name: twisted.web.test.test_template -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
HTML rendering for twisted.web.

@var VALID_HTML_TAG_NAMES: A list of recognized HTML tag names, used by the
    L{tag} object.

@var TEMPLATE_NAMESPACE: The XML namespace used to identify attributes and
    elements used by the templating system, which should be removed from the
    final output document.

@var tags: A convenience object which can produce L{Tag} objects on demand via
    attribute access.  For example: C{tags.div} is equivalent to C{Tag("div")}.
    Tags not specified in L{VALID_HTML_TAG_NAMES} will result in an
    L{AttributeError}.
"""


__all__ = [
    "TEMPLATE_NAMESPACE",
    "VALID_HTML_TAG_NAMES",
    "Element",
    "Flattenable",
    "TagLoader",
    "XMLString",
    "XMLFile",
    "renderer",
    "flatten",
    "flattenString",
    "tags",
    "Comment",
    "CDATA",
    "Tag",
    "slot",
    "CharRef",
    "renderElement",
]

import warnings

from collections import OrderedDict
from io import StringIO
from typing import (
    Any,
    AnyStr,
    Callable,
    Dict,
    IO,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
    cast,
)

from zope.interface import implementer

from xml.sax import make_parser, handler
from xml.sax.xmlreader import Locator

from twisted.internet.defer import Deferred
from twisted.python.failure import Failure
from twisted.python.filepath import FilePath
from twisted.web._stan import Tag, slot, Comment, CDATA, CharRef
from twisted.web.iweb import IRenderable, IRequest, ITemplateLoader
from twisted.logger import Logger

TEMPLATE_NAMESPACE = "http://twistedmatrix.com/ns/twisted.web.template/0.1"

# Go read the definition of NOT_DONE_YET. For lulz. This is totally
# equivalent. And this turns out to be necessary, because trying to import
# NOT_DONE_YET in this module causes a circular import which we cannot escape
# from. From which we cannot escape. Etc. glyph is okay with this solution for
# now, and so am I, as long as this comment stays to explain to future
# maintainers what it means. ~ C.
#
# See http://twistedmatrix.com/trac/ticket/5557 for progress on fixing this.
NOT_DONE_YET = 1
_moduleLog = Logger()


class _NSContext:
    """
    A mapping from XML namespaces onto their prefixes in the document.
    """

    def __init__(self, parent: Optional["_NSContext"] = None):
        """
        Pull out the parent's namespaces, if there's no parent then default to
        XML.
        """
        self.parent = parent
        if parent is not None:
            self.nss: Dict[Optional[str], Optional[str]] = OrderedDict(parent.nss)
        else:
            self.nss = {"http://www.w3.org/XML/1998/namespace": "xml"}

    def get(self, k: Optional[str], d: Optional[str] = None) -> Optional[str]:
        """
        Get a prefix for a namespace.

        @param d: The default prefix value.
        """
        return self.nss.get(k, d)

    def __setitem__(self, k: Optional[str], v: Optional[str]) -> None:
        """
        Proxy through to setting the prefix for the namespace.
        """
        self.nss.__setitem__(k, v)

    def __getitem__(self, k: Optional[str]) -> Optional[str]:
        """
        Proxy through to getting the prefix for the namespace.
        """
        return self.nss.__getitem__(k)


class _ToStan(handler.ContentHandler, handler.EntityResolver):
    """
    A SAX parser which converts an XML document to the Twisted STAN
    Document Object Model.
    """

    def __init__(self, sourceFilename: str):
        """
        @param sourceFilename: the filename to load the XML out of.
        """
        self.sourceFilename = sourceFilename
        self.prefixMap = _NSContext()
        self.inCDATA = False

    def setDocumentLocator(self, locator: Locator) -> None:
        """
        Set the document locator, which knows about line and character numbers.
        """
        self.locator = locator

    def startDocument(self) -> None:
        """
        Initialise the document.
        """
        # Depending on our active context, the element type can be Tag, slot
        # or str. Since mypy doesn't understand that context, it would be
        # a pain to not use Any here.
        self.document: List[Any] = []
        self.current = self.document
        self.stack: List[Any] = []
        self.xmlnsAttrs: List[Tuple[str, str]] = []

    def endDocument(self) -> None:
        """
        Document ended.
        """

    def processingInstruction(self, target: str, data: str) -> None:
        """
        Processing instructions are ignored.
        """

    def startPrefixMapping(self, prefix: Optional[str], uri: str) -> None:
        """
        Set up the prefix mapping, which maps fully qualified namespace URIs
        onto namespace prefixes.

        This gets called before startElementNS whenever an C{xmlns} attribute
        is seen.
        """

        self.prefixMap = _NSContext(self.prefixMap)
        self.prefixMap[uri] = prefix

        # Ignore the template namespace; we'll replace those during parsing.
        if uri == TEMPLATE_NAMESPACE:
            return

        # Add to a list that will be applied once we have the element.
        if prefix is None:
            self.xmlnsAttrs.append(("xmlns", uri))
        else:
            self.xmlnsAttrs.append(("xmlns:%s" % prefix, uri))

    def endPrefixMapping(self, prefix: Optional[str]) -> None:
        """
        "Pops the stack" on the prefix mapping.

        Gets called after endElementNS.
        """
        parent = self.prefixMap.parent
        assert parent is not None, "More prefix mapping ends than starts"
        self.prefixMap = parent

    def startElementNS(
        self,
        namespaceAndName: Tuple[str, str],
        qname: Optional[str],
        attrs: Mapping[Tuple[Optional[str], str], str],
    ) -> None:
        """
        Gets called when we encounter a new xmlns attribute.

        @param namespaceAndName: a (namespace, name) tuple, where name
            determines which type of action to take, if the namespace matches
            L{TEMPLATE_NAMESPACE}.
        @param qname: ignored.
        @param attrs: attributes on the element being started.
        """

        filename = self.sourceFilename
        lineNumber = self.locator.getLineNumber()
        columnNumber = self.locator.getColumnNumber()

        ns, name = namespaceAndName
        if ns == TEMPLATE_NAMESPACE:
            if name == "transparent":
                name = ""
            elif name == "slot":
                default: Optional[str]
                try:
                    # Try to get the default value for the slot
                    default = attrs[(None, "default")]
                except KeyError:
                    # If there wasn't one, then use None to indicate no
                    # default.
                    default = None
                sl = slot(
                    attrs[(None, "name")],
                    default=default,
                    filename=filename,
                    lineNumber=lineNumber,
                    columnNumber=columnNumber,
                )
                self.stack.append(sl)
                self.current.append(sl)
                self.current = sl.children
                return

        render = None

        attrs = OrderedDict(attrs)
        for k, v in list(attrs.items()):
            attrNS, justTheName = k
            if attrNS != TEMPLATE_NAMESPACE:
                continue
            if justTheName == "render":
                render = v
                del attrs[k]

        # nonTemplateAttrs is a dictionary mapping attributes that are *not* in
        # TEMPLATE_NAMESPACE to their values.  Those in TEMPLATE_NAMESPACE were
        # just removed from 'attrs' in the loop immediately above.  The key in
        # nonTemplateAttrs is either simply the attribute name (if it was not
        # specified as having a namespace in the template) or prefix:name,
        # preserving the xml namespace prefix given in the document.

        nonTemplateAttrs = OrderedDict()
        for (attrNs, attrName), v in attrs.items():
            nsPrefix = self.prefixMap.get(attrNs)
            if nsPrefix is None:
                attrKey = attrName
            else:
                attrKey = f"{nsPrefix}:{attrName}"
            nonTemplateAttrs[attrKey] = v

        if ns == TEMPLATE_NAMESPACE and name == "attr":
            if not self.stack:
                # TODO: define a better exception for this?
                raise AssertionError(
                    f"<{{{TEMPLATE_NAMESPACE}}}attr> as top-level element"
                )
            if "name" not in nonTemplateAttrs:
                # TODO: same here
                raise AssertionError(
                    f"<{{{TEMPLATE_NAMESPACE}}}attr> requires a name attribute"
                )
            el = Tag(
                "",
                render=render,
                filename=filename,
                lineNumber=lineNumber,
                columnNumber=columnNumber,
            )
            self.stack[-1].attributes[nonTemplateAttrs["name"]] = el
            self.stack.append(el)
            self.current = el.children
            return

        # Apply any xmlns attributes
        if self.xmlnsAttrs:
            nonTemplateAttrs.update(OrderedDict(self.xmlnsAttrs))
            self.xmlnsAttrs = []

        # Add the prefix that was used in the parsed template for non-template
        # namespaces (which will not be consumed anyway).
        if ns != TEMPLATE_NAMESPACE and ns is not None:
            prefix = self.prefixMap[ns]
            if prefix is not None:
                name = "{}:{}".format(self.prefixMap[ns], name)
        el = Tag(
            name,
            attributes=OrderedDict(
                cast(Mapping[Union[bytes, str], str], nonTemplateAttrs)
            ),
            render=render,
            filename=filename,
            lineNumber=lineNumber,
            columnNumber=columnNumber,
        )
        self.stack.append(el)
        self.current.append(el)
        self.current = el.children

    def characters(self, ch: str) -> None:
        """
        Called when we receive some characters.  CDATA characters get passed
        through as is.
        """
        if self.inCDATA:
            self.stack[-1].append(ch)
            return
        self.current.append(ch)

    def endElementNS(self, name: Tuple[str, str], qname: Optional[str]) -> None:
        """
        A namespace tag is closed.  Pop the stack, if there's anything left in
        it, otherwise return to the document's namespace.
        """
        self.stack.pop()
        if self.stack:
            self.current = self.stack[-1].children
        else:
            self.current = self.document

    def startDTD(self, name: str, publicId: str, systemId: str) -> None:
        """
        DTDs are ignored.
        """

    def endDTD(self, *args: object) -> None:
        """
        DTDs are ignored.
        """

    def startCDATA(self) -> None:
        """
        We're starting to be in a CDATA element, make a note of this.
        """
        self.inCDATA = True
        self.stack.append([])

    def endCDATA(self) -> None:
        """
        We're no longer in a CDATA element.  Collect up the characters we've
        parsed and put them in a new CDATA object.
        """
        self.inCDATA = False
        comment = "".join(self.stack.pop())
        self.current.append(CDATA(comment))

    def comment(self, content: str) -> None:
        """
        Add an XML comment which we've encountered.
        """
        self.current.append(Comment(content))


def _flatsaxParse(fl: Union[FilePath, IO[AnyStr], str]) -> List["Flattenable"]:
    """
    Perform a SAX parse of an XML document with the _ToStan class.

    @param fl: The XML document to be parsed.

    @return: a C{list} of Stan objects.
    """
    parser = make_parser()
    parser.setFeature(handler.feature_validation, 0)
    parser.setFeature(handler.feature_namespaces, 1)
    parser.setFeature(handler.feature_external_ges, 0)
    parser.setFeature(handler.feature_external_pes, 0)

    s = _ToStan(getattr(fl, "name", None))
    parser.setContentHandler(s)
    parser.setEntityResolver(s)
    parser.setProperty(handler.property_lexical_handler, s)

    parser.parse(fl)

    return s.document


@implementer(ITemplateLoader)
class TagLoader:
    """
    An L{ITemplateLoader} that loads an existing flattenable object.
    """

    def __init__(self, tag: "Flattenable"):
        """
        @param tag: The object which will be loaded.
        """

        self.tag: "Flattenable" = tag
        """The object which will be loaded."""

    def load(self) -> List["Flattenable"]:
        return [self.tag]


@implementer(ITemplateLoader)
class XMLString:
    """
    An L{ITemplateLoader} that loads and parses XML from a string.
    """

    def __init__(self, s: Union[str, bytes]):
        """
        Run the parser on a L{StringIO} copy of the string.

        @param s: The string from which to load the XML.
        @type s: L{str}, or a UTF-8 encoded L{bytes}.
        """
        if not isinstance(s, str):
            s = s.decode("utf8")

        self._loadedTemplate: List["Flattenable"] = _flatsaxParse(StringIO(s))
        """The loaded document."""

    def load(self) -> List["Flattenable"]:
        """
        Return the document.

        @return: the loaded document.
        """
        return self._loadedTemplate


@implementer(ITemplateLoader)
class XMLFile:
    """
    An L{ITemplateLoader} that loads and parses XML from a file.
    """

    def __init__(self, path: FilePath):
        """
        Run the parser on a file.

        @param path: The file from which to load the XML.
        """
        if not isinstance(path, FilePath):
            warnings.warn(  # type: ignore[unreachable]
                "Passing filenames or file objects to XMLFile is deprecated "
                "since Twisted 12.1.  Pass a FilePath instead.",
                category=DeprecationWarning,
                stacklevel=2,
            )

        self._loadedTemplate: Optional[List["Flattenable"]] = None
        """The loaded document, or L{None}, if not loaded."""

        self._path: FilePath = path
        """The file that is being loaded from."""

    def _loadDoc(self) -> List["Flattenable"]:
        """
        Read and parse the XML.

        @return: the loaded document.
        """
        if not isinstance(self._path, FilePath):
            return _flatsaxParse(self._path)  # type: ignore[unreachable]
        else:
            with self._path.open("r") as f:
                return _flatsaxParse(f)

    def __repr__(self) -> str:
        return f"<XMLFile of {self._path!r}>"

    def load(self) -> List["Flattenable"]:
        """
        Return the document, first loading it if necessary.

        @return: the loaded document.
        """
        if self._loadedTemplate is None:
            self._loadedTemplate = self._loadDoc()
        return self._loadedTemplate


# Last updated October 2011, using W3Schools as a reference. Link:
# http://www.w3schools.com/html5/html5_reference.asp
# Note that <xmp> is explicitly omitted; its semantics do not work with
# t.w.template and it is officially deprecated.
VALID_HTML_TAG_NAMES = {
    "a",
    "abbr",
    "acronym",
    "address",
    "applet",
    "area",
    "article",
    "aside",
    "audio",
    "b",
    "base",
    "basefont",
    "bdi",
    "bdo",
    "big",
    "blockquote",
    "body",
    "br",
    "button",
    "canvas",
    "caption",
    "center",
    "cite",
    "code",
    "col",
    "colgroup",
    "command",
    "datalist",
    "dd",
    "del",
    "details",
    "dfn",
    "dir",
    "div",
    "dl",
    "dt",
    "em",
    "embed",
    "fieldset",
    "figcaption",
    "figure",
    "font",
    "footer",
    "form",
    "frame",
    "frameset",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "head",
    "header",
    "hgroup",
    "hr",
    "html",
    "i",
    "iframe",
    "img",
    "input",
    "ins",
    "isindex",
    "keygen",
    "kbd",
    "label",
    "legend",
    "li",
    "link",
    "map",
    "mark",
    "menu",
    "meta",
    "meter",
    "nav",
    "noframes",
    "noscript",
    "object",
    "ol",
    "optgroup",
    "option",
    "output",
    "p",
    "param",
    "pre",
    "progress",
    "q",
    "rp",
    "rt",
    "ruby",
    "s",
    "samp",
    "script",
    "section",
    "select",
    "small",
    "source",
    "span",
    "strike",
    "strong",
    "style",
    "sub",
    "summary",
    "sup",
    "table",
    "tbody",
    "td",
    "textarea",
    "tfoot",
    "th",
    "thead",
    "time",
    "title",
    "tr",
    "tt",
    "u",
    "ul",
    "var",
    "video",
    "wbr",
}


class _TagFactory:
    """
    A factory for L{Tag} objects; the implementation of the L{tags} object.

    This allows for the syntactic convenience of C{from twisted.web.html import
    tags; tags.a(href="linked-page.html")}, where 'a' can be basically any HTML
    tag.

    The class is not exposed publicly because you only ever need one of these,
    and we already made it for you.

    @see: L{tags}
    """

    def __getattr__(self, tagName: str) -> Tag:
        if tagName == "transparent":
            return Tag("")
        # allow for E.del as E.del_
        tagName = tagName.rstrip("_")
        if tagName not in VALID_HTML_TAG_NAMES:
            raise AttributeError(f"unknown tag {tagName!r}")
        return Tag(tagName)


tags = _TagFactory()


def renderElement(
    request: IRequest,
    element: IRenderable,
    doctype: Optional[bytes] = b"<!DOCTYPE html>",
    _failElement: Optional[Callable[[Failure], "Element"]] = None,
) -> object:
    """
    Render an element or other L{IRenderable}.

    @param request: The L{IRequest} being rendered to.
    @param element: An L{IRenderable} which will be rendered.
    @param doctype: A L{bytes} which will be written as the first line of
        the request, or L{None} to disable writing of a doctype.  The argument
        should not include a trailing newline and will default to the HTML5
        doctype C{'<!DOCTYPE html>'}.

    @returns: NOT_DONE_YET

    @since: 12.1
    """
    if doctype is not None:
        request.write(doctype)
        request.write(b"\n")

    if _failElement is None:
        _failElement = twisted.web.util.FailureElement

    d = flatten(request, element, request.write)

    def eb(failure: Failure) -> Optional[Deferred[None]]:
        _moduleLog.failure(
            "An error occurred while rendering the response.", failure=failure
        )
        site: Optional["twisted.web.server.Site"] = getattr(request, "site", None)
        if site is not None and site.displayTracebacks:
            assert _failElement is not None
            return flatten(request, _failElement(failure), request.write)
        else:
            request.write(
                b'<div style="font-size:800%;'
                b"background-color:#FFF;"
                b"color:#F00"
                b'">An error occurred while rendering the response.</div>'
            )
            return None

    def finish(result: object, *, request: IRequest = request) -> object:
        request.finish()
        return result

    d.addErrback(eb)
    d.addBoth(finish)
    return NOT_DONE_YET


from twisted.web._element import Element, renderer
from twisted.web._flatten import Flattenable, flatten, flattenString
import twisted.web.util
