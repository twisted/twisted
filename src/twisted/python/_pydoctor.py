# -*- test-case-name: twisted.python.test.test_pydoctor -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for a few things specific to documenting Twisted using pydoctor.

FIXME: https://github.com/twisted/pydoctor/issues/106
This documentation does not link to pydoctor API as there is no public API yet.
"""

import ast
from typing import Optional

from pydoctor import model, zopeinterface, astbuilder
from pydoctor.sphinx import SphinxInventory


class TwistedSphinxInventory(SphinxInventory):
    """
    Custom SphinxInventory to work around broken external references to
    Sphinx.

    All exceptions should be reported upstream and a comment should be created
    with a link to the upstream report.
    """

    def getLink(self, name):
        """
        Resolve the full URL for a cross reference.

        @param name: Value of the cross reference.
        @type name: L{str}

        @return: A full URL for the I{name} reference or L{None} if no link was
            found.
        @rtype: L{str} or L{None}
        """
        result = super().getLink(name)
        if result is not None:
            # We already got a link. Look no further.
            return result

        if name.startswith("zope.interface."):
            # This is a link from zope.interface. which is not advertised in
            # the Sphinx inventory.
            # See if the link is a known broken link which should be handled
            # as an exceptional case.
            # We get the base URL from IInterface which is assume that is
            # always and already well defined in the Sphinx index.
            baseURL, _ = self._links.get(
                "zope.interface.interfaces.IInterface", (None, None)
            )

            if baseURL is None:
                # Most probably the zope.interface inventory was
                # not loaded.
                return None

            if name == "zope.interface.adapter.AdapterRegistry":
                # FIXME:
                # https://github.com/zopefoundation/zope.interface/issues/41
                relativeLink = "adapter.html"  # type: Optional[str]
            else:
                # Not a known exception.
                relativeLink = None

            if relativeLink is None:
                return None

            return "{}/{}".format(baseURL, relativeLink)

        return None


def getDeprecated(self, decorators):
    """
    With a list of decorators, and the object it is running on, set the
    C{_deprecated_info} flag if any of the decorators are a Twisted deprecation
    decorator.
    """
    for a in decorators:
        if isinstance(a, ast.Call):
            fn = astbuilder.node2fullname(a.func, self)

            if fn in (
                "twisted.python.deprecate.deprecated",
                "twisted.python.deprecate.deprecatedProperty",
            ):
                try:
                    self._deprecated_info = deprecatedToUsefulText(self, self.name, a)
                except AttributeError:
                    # It's a reference or something that we can't figure out
                    # from the AST.
                    pass


class TwistedModuleVisitor(zopeinterface.ZopeInterfaceModuleVisitor):
    def visit_ClassDef(self, node):
        """
        Called when a class definition is visited.
        """
        super().visit_ClassDef(node)
        try:
            cls = self.builder.current.contents[node.name]
        except KeyError:
            # Classes inside functions are ignored.
            return

        getDeprecated(cls, cls.raw_decorators)

    def visit_FunctionDef(self, node):
        """
        Called when a function definition is visited.
        """
        super().visit_FunctionDef(node)
        try:
            func = self.builder.current.contents[node.name]
        except KeyError:
            # Inner functions are ignored.
            return

        if func.decorators:
            getDeprecated(func, func.decorators)


def versionToUsefulObject(version):
    """
    Change an AST C{Version()} to a real one.
    """
    from incremental import Version

    package = version.args[0].s
    major = getattr(version.args[1], "n", getattr(version.args[1], "s", None))
    return Version(package, major, *(x.n for x in version.args[2:] if x))


def deprecatedToUsefulText(visitor, name, deprecated):
    """
    Change a C{@deprecated} to a display string.
    """
    from twisted.python.deprecate import _getDeprecationWarningString

    version = versionToUsefulObject(deprecated.args[0])
    if len(deprecated.args) > 1 and deprecated.args[1]:
        if isinstance(deprecated.args[1], ast.Name):
            replacement = visitor.resolveName(deprecated.args[1].id)
        else:
            replacement = deprecated.args[1].s
    else:
        replacement = None
        for keyword in deprecated.keywords:
            if keyword.arg == "replacement":
                replacement = keyword.value.s

    return _getDeprecationWarningString(name, version, replacement=replacement) + "."


class TwistedASTBuilder(zopeinterface.ZopeInterfaceASTBuilder):
    # Vistor is not a typo...
    ModuleVistor = TwistedModuleVisitor


class TwistedSystem(zopeinterface.ZopeInterfaceSystem):
    """
    A PyDoctor "system" used to generate the docs.
    """

    defaultBuilder = TwistedASTBuilder

    def __init__(self, options=None):
        super().__init__(options=options)
        # Use custom SphinxInventory so that we can resolve valid L{} markup
        # for which the Sphinx inventory is not published or broken.
        self.intersphinx = TwistedSphinxInventory(
            logger=self.msg, project_name=self.projectname
        )

    def privacyClass(self, documentable):
        """
        Report the privacy level for an object.

        Hide all tests with the exception of L{twisted.test.proto_helpers}.

        param obj: Object for which the privacy is reported.
        type obj: C{model.Documentable}

        rtype: C{model.PrivacyClass} member
        """
        if documentable.fullName() == "twisted.test":
            # Match this package exactly, so that proto_helpers
            # below is visible
            return model.PrivacyClass.VISIBLE

        current = documentable
        while current:
            if current.fullName() == "twisted.test.proto_helpers":
                return model.PrivacyClass.VISIBLE
            if isinstance(current, model.Package) and current.name == "test":
                return model.PrivacyClass.HIDDEN
            current = current.parent

        return super().privacyClass(documentable)
