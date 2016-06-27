# -*- test-case-name: twisted.python.test.test_pydoctor -*-
# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

"""
Support for a few things specific to documenting Twisted using pydoctor.
"""

from pydoctor import model, ast_pp, zopeinterface
from pydoctor.sphinx import SphinxInventory



class TwistedModuleVisitor(zopeinterface.ZopeInterfaceModuleVisitor):

    def visitCallFunc_twisted_python_util_moduleMovedForSplit(self, funcName, node):
        # XXX this is rather fragile...
        origModuleName, newModuleName, moduleDesc, \
                        projectName, projectURL, globDict = node.args
        moduleDesc = ast_pp.pp(moduleDesc)[1:-1]
        projectName = ast_pp.pp(projectName)[1:-1]
        projectURL = ast_pp.pp(projectURL)[1:-1]
        modoc = """
%(moduleDesc)s

This module is DEPRECATED. It has been split off into a third party
package, Twisted %(projectName)s. Please see %(projectURL)s.

This is just a place-holder that imports from the third-party %(projectName)s
package for backwards compatibility. To use it, you need to install
that package.
""" % {'moduleDesc': moduleDesc,
       'projectName': projectName,
       'projectURL': projectURL}
        self.builder.current.docstring = modoc



class TwistedASTBuilder(zopeinterface.ZopeInterfaceASTBuilder):
    ModuleVistor = TwistedModuleVisitor



class TwistedSphinxInventory(SphinxInventory):
    """
    Custom SphinxInventory to work around broken external references to
    Sphinx.
    """

    def getLink(self, name):
        """
        Return URL for `name` or None if no URL is found.
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
            base_url, _ = self._links.get(
                'zope.interface.interfaces.IInterface')

            if name  == 'zope.interface.adapter.AdapterRegistry':
                relative_link = 'adapter.html'
            else:
                # Not a known exception.
                relative_link = None

            if relative_link is None:
                return None

            return '%s/%s' % (base_url, relative_link)

        return result



class TwistedSystem(zopeinterface.ZopeInterfaceSystem):
    """
    Maybe class used to set up all pydoctor system.
    """
    defaultBuilder = TwistedASTBuilder

    def __init__(self, options=None):
        super(TwistedSystem, self).__init__(options=options)
        # Use custom SphinxInventory so that we can resolve valid L{} markup
        # for which the Sphinx inventory is not published or broken.
        self.intersphinx = TwistedSphinxInventory(
            logger=self.msg, project_name=self.projectname)

    def privacyClass(self, obj):
        o = obj
        if o.fullName() == 'twisted.test':
            # Match this package exactly, so that proto_helpers
            # below is visible
            return model.PrivacyClass.VISIBLE
        while o:
            if o.fullName() == 'twisted.words.xish.yappsrt':
                return model.PrivacyClass.HIDDEN
            if o.fullName() == 'twisted.test.proto_helpers':
                return model.PrivacyClass.VISIBLE
            if isinstance(o, model.Package) and o.name == 'test':
                return model.PrivacyClass.HIDDEN
            o = o.parent
        return super(TwistedSystem, self).privacyClass(obj)
