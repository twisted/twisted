# domcontrollers

import os

from twisted.python.mvc import Controller

class InputHandler(Controller):
    """
    A handler is like a controller, but it operates on something contained inside
    of self.model instead of directly on self.model. For example, a Handler whose
    id has been set to "foo" will handle self.model.foo
    
    The handler's job is to interpret the request and:
    
    1) Check for valid input
    2) If the input is valid, update the model
    3) Use any special API of the view widget to change the view (other than what the
        view updates automatically from the model)
        e.g. in the case of an error, tell the view to report an error to the user
    4) Return a success value; by default these values are simply recorded and
        the page is rendered, but these values could be used to determine what
        page to display next, etc
    """
    def setId(self, id):
        print "setId is deprecated; please use setSubmodel."
        self.submodel = id
        
    def setSubmodel(self, submodel):
        self.submodel = submodel

    def getInput(self, request):
        """
        Return the data associated with this handler from the request, if any
        """
        input = request.args.get(self.submodel, None)
        if input:
            return input

    def handle(self, request):
        data = self.getInput(request)
        success = self.check(request, data)
        if success is not None:
            if success:
                self.handleValid(request, data)
            else:
                self.handleInvalid(request, data)
        return (success, data)

    def check(self, request, data):
        """
        Check whether the input in the request is valid for this handler
        and return a boolean indicating validity.
        """
        raise NotImplementedError
    
    def handleValid(self, request, data):
        """
        It has been determined that the input for this handler is valid;
        however, that does not mean the entire form is valid.
        """
        pass

    def handleInvalid(self, request, data):
        """
        Once it has been determined that the input is invalid, we should
        tell our view to report this fact to the user.
        """
        self.view.setError("Error!")

    def commit(self, request, node, data):
        """
        It has been determined that the input for the entire form is completely
        valid; it is now safe for all handlers to commit changes to the model.
        """
        if not self.submodel or not self.model: return
        data = str(data)
        assert ';' not in self.submodel, "Semicolon is not legal in handler ids."

        if data != self.view.getData():
            exec "self.model." + self.submodel + " = " + `data`
            self.model.notify({self.submodel: data})

class SingleValue(InputHandler):
    def getInput(self, request):
        input = request.args.get(self.submodel, None)
        if input:
            return input[0]

SingleValueInputHandler = SingleValue

class Anything(SingleValue):
    """
    Handle anything except for None
    """
    def check(self, request, data):
        if data is not None:
            return 1
        return None

AnythingInputHandler = Anything

class Integer(SingleValue):
    """
    Only allow a single integer
    """
    def check(self, request, data):
        if data is None: return None
        try:
            int(data)
            return 1
        except (TypeError, ValueError):
            return 0

    def handleInvalid(self, request, data):
        if data is not None:
            self.view.setError("%s is not an integer. Please enter an integer." % data)

IntHandler = Integer

class Float(SingleValue):
    """
    Only allow a single float
    """
    def check(self, request, data):
        if data is None: return None
        try:
            float(data)
            return 1
        except (TypeError, ValueError):
            return 0

    def handleInvalid(self, request, data):
        if data is not None:
            self.view.setError("%s is not an float. Please enter a float." % data)

FloatHandler = Float

class List(InputHandler):        
    def check(self, request, data):
        return None

ListHandler = List

class NewObject(SingleValue):
    """
    Check to see if the name the user entered is valid.
    If it is, create the object. If not, tell the user why.
    """
    classToCreate = None
    
    def check(self, request, name):
        """
        Check to see if the name the user typed is a valid object name.
        """
        if name is None: return None

        if name[0] is '_':
            self.errorReason = "An object's name must not start with an underscore."
            return 0
        parentRef = request.pathRef().parentRef()
        if name + '.trp' not in os.listdir(parentRef.diskPath()):
            return 1
        else:
            self.errorReason = "The name %s is already in use." % name
        return 0
    
    def handleValid(self, request, name):
        """
        The user has entered a valid project name and chosen to create the project.
        Get a reference to the parent folder, create a new Project instance, and
        pickle it.
        """
        assert self.classToCreate is not None, "To use the NewObject handler, you must supply a classToCreate."
        parent = request.pathRef().parentRef().getObject()
        project = self.classToCreate(projectName = name)
        parent.createPickleChild(name, project)

    def handleInvalid(self, request, name):
        """
        The user has entered an invalid project name.
        """
        self.view.setError(self.errorReason)

NewObjectHandler = NewObject
