# -*- test-case-name: twisted.web.test.test_util -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
An assortment of web server-related utilities.
"""

__all__ = [
    "redirectTo",
    "Redirect",
    "ChildRedirector",
    "ParentRedirect",
    "DeferredResource",
    "FailureElement",
    "formatFailure",
]

from ._template_util import (
    ChildRedirector,
    DeferredResource,
    FailureElement,
    ParentRedirect,
    Redirect,
    formatFailure,
    redirectTo,
)
