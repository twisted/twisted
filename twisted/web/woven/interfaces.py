from twisted.python import components

class IModel(components.Interface):
    """A MVC Model."""
    def addView(view):
        """Add a view for the model to keep track of."""

    def removeView(view):
        """Remove a view that the model no longer should keep track of."""

    def notify(changed=None):
        """
        Notify all views that something was changed on me.
        Passing a dictionary of {'attribute': 'new value'} in changed
        will pass this dictionary to the view for increased performance.
        If you don't want to do this, don't, and just use the traditional
        MVC paradigm of querying the model for things you're interested
        in.
        """

class IView(components.Interface):
    """A MVC View"""
    def __init__(model, controller=None):
        """
        A view must be told what its model is, and may be told what its
        controller is, but can also look up its controller if none specified.
        """

    def modelChanged(changed):
        """
        Dispatch changed messages to any update_* methods which
        may have been defined, then pass the update notification on
        to the controller.
        """

    def controllerFactory():
        """
        Hook for subclasses to customize the controller that is associated
        with the model associated with this view.
        
        Default behavior: Look up a component that implements IController
        for the self.model instance.
        """
        
    def setController(controller):
        """Set the controller that this view is related to."""

    def lookupSubmodel(name):
        """Get a submodel out of this model by name.
        """
    
    def setSubmodel(name, value):
        """Set the named submodel on this model to the given value.
        """

    def getData():
        """
        @return: The actual data (or a L{twisted.internet.defer.Deferred}
                 resulting in the actual data) represented by this Model,
                 if this model is just a wrapper. Otherwise, return self.
        """
    
    def setData(data):
        """Set the actual data represented by this Model wrapper. This
        model must have a parent reference obtained by using lookupSubmodel
        for this to work.
        """


class IController(components.Interface):
    """A MVC Controller"""
    def setView(view):
        """
        Set the view that this controller is related to.
        """
