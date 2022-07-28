# -*- test-case-name: twisted.python.test.test_pydoctor -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for a few things specific to documenting Twisted using pydoctor.

See L{pydoctor} for details.
"""

from typing import Optional

from pydoctor import model  # type: ignore[import]
from pydoctor.sphinx import SphinxInventory  # type: ignore[import]


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
                relativeLink: Optional[str] = "adapter.html"
            else:
                # Not a known exception.
                relativeLink = None

            if relativeLink is None:
                return None

            return f"{baseURL}/{relativeLink}"

        return None


class TwistedSystem(model.System):
    """
    A PyDoctor "system" used to generate the docs.
    """

    def __init__(self, options=None):
        super().__init__(options=options)
        # Use custom SphinxInventory so that we can resolve valid L{} markup
        # for which the Sphinx inventory is not published or broken.
        self.intersphinx = TwistedSphinxInventory(
            logger=self.msg, project_name=self.projectname
        )
