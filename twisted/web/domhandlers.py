# domcontrollers

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
    """
    def setId(self, id):
        self.id = id

    def getInput(self, request):
        """
        Return the data associated with this handler from the request, if any
        """
        input = request.args.get(self.id, None)
        if input:
            return input

    def handle(self, request):
        data = self.getInput(request)
        result = self.check(data)
        if result is not None:
            if result:
                # success
                self.handleValid(data, request)
            else:
                # fail
                self.handleInvalid(data, request)
        return self.view.render(request)
    
    def check(self, data):
        """
        Check whether the input in the request is valid for this handler
        and return a boolean indicating validity.
        """
        raise NotImplementedError
    
    def handleValid(self, data, request):
        """
        Take a request and do something with it
        
        -- set the model?
        """
        data = str(data)
        assert ';' not in self.id, "Semicolon is not legal in handler ids."
        if data != self.view.getData():
            exec "self.model." + self.id + " = " + `data`
#        setattr(self.model, self.id, data)
            self.model.notify({self.id: data})

    def handleInvalid(self, data, request):
        """
        Do something if the input was invalid?
        """
        self.view.setError("Error!")


class SingleValueInputHandler(InputHandler):
    def getInput(self, request):
        input = request.args.get(self.id, None)
        if input:
            return input[0]

class AnythingInputHandler(SingleValueInputHandler):
    """
    Handle anything except for None
    """
    def check(self, data):
        if data is not None:
            return 1
        return None

class IntHandler(SingleValueInputHandler):
    """
    Only allow a single integer
    """
    def check(self, data):
        try:
            int(data)
            return 1
        except (TypeError, ValueError):
            return 0

    def handleInvalid(self, data, request):
        if data is not None:
            self.view.setError("%s is not an integer. Please enter an integer." % data)

class FloatHandler(SingleValueInputHandler):
    """
    Only allow a single float
    """
    def check(self, data):
        try:
            float(data)
            return 1
        except (TypeError, ValueError):
            return 0

    def handleInvalid(self, data, request):
        if data is not None:
            self.view.setError("%s is not an float. Please enter a float." % data)
