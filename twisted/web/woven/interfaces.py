from twisted.python import components

class IModel(components.Interface):
    """A MVC Model."""
    def addView(view):
        """Add a view for the model to keep track of.
        """

    def addSubview(view, subviewName):
        """Add a view for the model to keep track of. This model will only
        be notified if "subviewName"'s data has changed.
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

    def getData(self):
        """Return the raw data contained by this Model object, if it is a
        wrapper. If not, return self.
        """

    def setData(self, data):
        """Set the raw data referenced by this Model object, if it is a
        wrapper. This is done by telling our Parent model to setSubmodel
        the new data. If this object is not a wrapper, keep the data
        around and return it for subsequent getData calls.
        """

    def lookupSubmodel(self, submodelPath):
        """Return an IModel implementor for the given submodel path
        string. This path may be any number of elements separated
        by /. The default implementation splits on "/" and calls
        getSubmodel until the path is exhausted. You will not normally
        need to override this behavior.
        """

    def getSubmodel(self, submodelName):
        """Return an IModel implementor for the submodel named
        "submodelName". If this object contains simple data types,
        they can be adapted to IModel using
        model.adaptToIModel(m, parent, name) before returning.
        """

    def setSubmodel(self, submodelName, data):
        """Set the given data as a submodel of this model. The data
        need not implement IModel, since getSubmodel should adapt
        the data to IModel before returning it.
        """


class IView(components.Interface):
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


class IController(components.Interface):
    """A MVC Controller"""
    def setView(view):
        """Set the view that this controller is related to.
        """
