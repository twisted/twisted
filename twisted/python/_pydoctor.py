# -*- test-case-name: twisted.python.test.test_pydoctor -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for a few things specific to documenting Twisted using pydoctor.

FIXME: https://github.com/twisted/pydoctor/issues/106
This documentation does not link to pydoctor API as there is no public API yet.
"""

from pydoctor import model, zopeinterface
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
        result = super(TwistedSphinxInventory, self).getLink(name)
        if result is not None:
            # We already got a link. Look no further.
            return result

        if name.startswith('zope.interface.'):
            # This is a link from zope.interface. which is not advertised in
            # the Sphinx inventory.
            # See if the link is a known broken link which should be handled
            # as an exceptional case.
            # We get the base URL from IInterface which is assume that is
            # always and already well defined in the Sphinx index.
            baseURL, _ = self._links.get(
                'zope.interface.interfaces.IInterface')

            if name  == 'zope.interface.adapter.AdapterRegistry':
                # FIXME:
                # https://github.com/zopefoundation/zope.interface/issues/41
                relativeLink = 'adapter.html'
            else:
                # Not a known exception.
                relativeLink = None

            if relativeLink is None:
                return None

            return '%s/%s' % (baseURL, relativeLink)

        return None



class TwistedSystem(zopeinterface.ZopeInterfaceSystem):
    """
    Maybe class used to set up all pydoctor system.
    """

    def __init__(self, options=None):
        super(TwistedSystem, self).__init__(options=options)
        # Use custom SphinxInventory so that we can resolve valid L{} markup
        # for which the Sphinx inventory is not published or broken.
        self.intersphinx = TwistedSphinxInventory(
            logger=self.msg, project_name=self.projectname)


    def privacyClass(self, documentable):
        """
        Report the privacy level for an object.

        Hide all tests with the exception of L{twisted.test.proto_helpers}.

        param obj: Object for which the privacy is reported.
        type obj: C{model.Documentable}

        rtype: C{model.PrivacyClass} member
        """

        if documentable.fullName() == 'twisted.test':
            # Match this package exactly, so that proto_helpers
            # below is visible
            return model.PrivacyClass.VISIBLE

        current = documentable
        while current:
            if current.fullName() == 'twisted.test.proto_helpers':
                return model.PrivacyClass.VISIBLE
            if isinstance(current, model.Package) and current.name == 'test':
                return model.PrivacyClass.HIDDEN
            current = current.parent

        return super(TwistedSystem, self).privacyClass(documentable)
