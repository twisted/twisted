# -*- test-case-name: twisted.web.test.test_pages -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Utility implementations of L{IResource}.
"""

__all__ = (
    "ErrorPage",
    "notFound",
    "forbidden",
)

from typing import cast

from twisted.web import http
from twisted.web.iweb import IRenderable, IRequest
from twisted.web.resource import Resource
from twisted.web.template import renderElement, tags


class ErrorPage(Resource):
    """
    L{ErrorPage} is a resource that responds to all requests with a particular
    (parameterized) HTTP status code and a body consisting of HTML containing
    some descriptive text. This is useful for rendering simple error pages.

    @ivar _code: An integer HTTP status code which will be used for the
        response.

    @ivar _brief: A short string which will be included in the response body as
        the page title.

    @ivar _detail: A longer string which will be included in the response body.
    """

    def __init__(self, code: int, brief: str, detail: str) -> None:
        """
        @param code: An integer HTTP status code which will be used for the
            response.

        @param brief: A short string which will be included in the response
            body as the page title.

        @param detail: A longer string which will be included in the
            response body.
        """
        super().__init__()
        self._code: int = code
        self._brief: str = brief
        self._detail: str = detail

    def render(self, request: IRequest) -> object:
        """
        Respond to all requests with the given HTTP status code and an HTML
        document containing the explanatory strings.
        """
        request.setResponseCode(self._code)
        request.setHeader(b"content-type", b"text/html; charset=utf-8")
        return renderElement(
            request,
            # cast because the type annotations here seem off; Tag isn't an
            # IRenderable but also probably should be? See
            # https://github.com/twisted/twisted/issues/4982
            cast(
                IRenderable,
                tags.html(
                    tags.head(tags.title(f"{self._code} - {self._brief}")),
                    tags.body(tags.h1(self._brief), tags.p(self._detail)),
                ),
            ),
        )

    def getChild(self, path: bytes, request: IRequest) -> Resource:
        """
        Handle all requests for which L{ErrorPage} lacks a child by returning
        this error page.

        @param path: A path segment.

        @param request: HTTP request
        """
        return self


def notFound(
    brief: str = "No Such Resource",
    message: str = "Sorry. No luck finding that resource.",
) -> ErrorPage:
    """
    Generate an L{ErrorPage} with a 404 Not Found status code.

    @param brief: A short string displayed as the page title.

    @param brief: A longer string displayed in the page body.

    @returns: An L{ErrorPage}
    """
    return ErrorPage(http.NOT_FOUND, brief, message)


def forbidden(
    brief: str = "Forbidden Resource", message: str = "Sorry, resource is forbidden."
) -> ErrorPage:
    """
    Generate an L{ErrorPage} with a 403 Forbidden status code.

    @param brief: A short string displayed as the page title.

    @param brief: A longer string displayed in the page body.

    @returns: An L{ErrorPage}
    """
    return ErrorPage(http.FORBIDDEN, brief, message)
