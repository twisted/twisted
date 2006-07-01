# -*- test-case-name: twisted.web.test.test_woven -*-

__version__ = "$Revision: 1.13 $"[11:-2]

from zope.interface import Interface

class IModel(Interface):
    """A MVC Model."""
    def addView(view):
        """Add a view for the model to keep track of.
        """

    def removeView(view):
        """Remove a view that the model no longer should keep track of.
        """

    def notify(changed=None):
        """Notify all views that something was changed on me.
        Passing a dictionary of {'attribute': 'new value'} in changed
        will pass this dictionary to the view for increased performance.
        If you don't want to do this, don't, and just use the traditional
        MVC paradigm of querying the model for things you're interested
        in.
        """

    def getData():
        """Return the raw data contained by this Model object, if it is a
        wrapper. If not, return self.
        """

    def setData(request, data):
        """Set the raw data referenced by this Model object, if it is a
        wrapper. This is done by telling our Parent model to setSubmodel
        the new data. If this object is not a wrapper, keep the data
        around and return it for subsequent getData calls.
        """

    def lookupSubmodel(request, submodelPath):
        """Return an IModel implementor for the given submodel path
        string. This path may be any number of elements separated
        by /. The default implementation splits on "/" and calls
        getSubmodel until the path is exhausted. You will not normally
        need to override this behavior.
        """

    def getSubmodel(request, submodelName):
        """Return an IModel implementor for the submodel named
        "submodelName". If this object contains simple data types,
        they can be adapted to IModel using
        model.adaptToIModel(m, parent, name) before returning.
        """

    def setSubmodel(request, submodelName, data):
        """Set the given data as a submodel of this model. The data
        need not implement IModel, since getSubmodel should adapt
        the data to IModel before returning it.
        """


class IView(Interface):
    """A MVC View"""
    def __init__(model, controller=None):
        """A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """

    def modelChanged(changed):
        """Dispatch changed messages to any update_* methods which
        may have been defined, then pass the update notification on
        to the controller.
        """

    def controllerFactory():
        """Hook for subclasses to customize the controller that is associated
        with the model associated with this view.

        Default behavior: Look up a component that implements IController
        for the self.model instance.
        """

    def setController(controller):
        """Set the controller that this view is related to."""

    def importViewLibrary(moduleOrObject):
        """Import the given object or module into this View's view namespace
        stack. If the given object or module has a getSubview function or
        method, it will be called when a node has a view="foo" attribute.
        If no getSubview method is defined, a default one will be provided
        which looks for the literal name in the namespace.
        """

    def getSubview(request, node, model, viewName):
        """Look for a view named "viewName" to handle the node "node".
        When a node <div view="foo" /> is present in the template, this
        method will be called with viewName set to "foo".

        Return None if this View doesn't want to provide a Subview for
        the given name.
        """

    def setSubviewFactory(name, factory, setup=None):
        """Set the callable "factory", which takes a model and should
        return a Widget, to be called by the default implementation of
        getSubview when the viewName "name" is present in the template.

        This would generally be used like this:

        view.setSubviewFactory("foo", MyFancyWidgetClass)

        This is equivalent to::

            def wvfactory_foo(self, request, node, m):
                return MyFancyWidgetClass(m)

        Which will cause an instance of MyFancyWidgetClass to be
        instanciated when template node <div view="foo" /> is encountered.

        If setup is passed, it will be passed to new instances returned
        from this factory as a setup method. The setup method is called
        each time the Widget is generated. Setup methods take (request,
        widget, model) as arguments.

        This is equivalent to::

            def wvupdate_foo(self, request, widget, model):
                # whatever you want
        """

    def __adapt__(adaptable, default):
        if hasattr(adaptable, 'original'):
            return IView(adaptable.original, default)
        return default


class IController(Interface):
    """A MVC Controller"""
    def setView(view):
        """Set the view that this controller is related to.
        """

    def importControllerLibrary(moduleOrObject):
        """Import the given object or module into this Controllers's
        controller namespace stack. If the given object or module has a
        getSubcontroller function or method, it will be called when a node
        has a controller="foo" attribute. If no getSubcontroller method is
        defined, a default one will be provided which looks for the literal
        name in the namespace.
        """

    def getSubcontroller(request, node, model, controllerName):
        """Look for a controller named "controllerName" to handle the node
        "node". When a node <div controller="foo" /> is present in the
        template, this method will be called with controllerName set to "foo".

        Return None if this Controller doesn't want to provide a Subcontroller
        for the given name.
        """

    def setSubcontrollerFactory(name, factory):
        """Set the callable "factory", which takes a model and should
        return an InputHandler, to be called by the default implementation of
        getSubview when the controllerName "name" is present in the template.

        This would generally be used like this::

            view.setSubcontrollerFactory("foo", MyFancyInputHandlerClass)

        This is equivalent to::

            def wcfactory_foo(self, request, node, m):
                return MyFancyInputHandlerClass(m)

        Which will cause an instance of MyFancyInputHandlerClass to be
        instanciated when template node <div controller="foo" /> is
        encountered.
        """

    def __adapt__(adaptable, default):
        if hasattr(adaptable, 'original'):
            return IController(adaptable.original, default)
        return default


class IWovenLivePage(Interface):
    def getCurrentPage():
        """Return the current page object contained in this session.
        """

    def setCurrentPage(page):
        """Set the current page object contained in this session.
        """

    def sendJavaScript(js):
        """Send "js" to the live page's persistent output conduit for
        execution in the browser. If there is no conduit connected yet, 
        save the js and write it as soon as the output conduit is 
        connected.
        """
