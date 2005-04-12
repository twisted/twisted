# -*- test-case-name: twisted.web.test.test_woven -*-
#
# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


# dominput

import os
import inspect

from twisted.internet import defer
from twisted.python import log
from twisted.python.reflect import qual

from twisted.web import domhelpers
from twisted.web.woven import template, controller, utils

__version__ = "$Revision: 1.34 $"[11:-2]

controllerFactory = controller.controllerFactory


class InputHandler(controller.Controller):
    """
    An InputHandler is like a controller, but it operates on something
    contained inside of C{self.model} instead of directly on C{self.model}.
    For example, a Handler whose C{model} has been set to C{"foo"} will handle
    C{self.model.foo}.

    The handler's job is to interpret the request and:

        1. Check for valid input
        2. If the input is valid, update the model
        3. Use any special API of the view widget to change the view (other
           than what the view updates automatically from the model) e.g. in the
           case of an error, tell the view to report an error to the user
        4. Return a success value; by default these values are simply recorded
           and the page is rendered, but these values could be used to determine
           what page to display next, etc.
    """
    invalidErrorText = "Error!"
    setupStacks = 0
    def __init__(self, model=None, 
                parent=None, 
                name=None,
                check=None, 
                commit = None, 
                invalidErrorText = None, 
                submodel=None,
                controllerStack=None):
        self.controllerStack = controllerStack
        controller.Controller.__init__(self, model)
        self._check = check
        self._commit = commit
        self._errback = None
        self._parent = parent
        if invalidErrorText is not None:
            self.invalidErrorText = invalidErrorText
        if submodel is not None:
            self.submodel = submodel
        if name is not None:
            self.inputName = name

    def initialize(self):
        pass

    def setNode(self, node):
        self.node = node

    def getInput(self, request):
        """
        Return the data associated with this handler from the request, if any.
        """
        name = getattr(self, 'inputName', self.submodel)
        input = request.args.get(name, None)
        if input:
            return input

    def handle(self, request):
        self.initialize()
        data = self.getInput(request)
        success = self.check(request, data)
        if isinstance(success, defer.Deferred):
            success.addCallback(self.dispatchCheckResult, request, data)
            success.addErrback(utils.renderFailure, request)
            return success
        self.dispatchCheckResult(success, request, data)

    def dispatchCheckResult(self, success, request, data):
        if success is not None:
            if success:
                result = self.handleValid(request, data)
            else:
                result = self.handleInvalid(request, data)
            if isinstance(result, defer.Deferred):
                return result

    def check(self, request, data):
        """
        Check whether the input in the request is valid for this handler
        and return a boolean indicating validity.
        """
        if self._check is None:
            raise NotImplementedError(qual(self.__class__)+'.check')
        # self._check is probably a bound method or simple function that
        # doesn't have a reference to this InputHandler; pass it
        return self._check(self, request, data)

    def handleValid(self, request, data):
        """
        It has been determined that the input for this handler is valid;
        however, that does not mean the entire form is valid.
        """
        self._parent.aggregateValid(request, self, data)

    def aggregateValid(self, request, inputhandler, data):
        """By default we just pass the method calls all the way up to the root
        Controller. However, an intelligent InputHandler could override this
        and implement a state machine that waits for all data to be collected
        and then fires.
        """
        self._parent.aggregateValid(request, inputhandler, data)
 
    def handleInvalid(self, request, data):
        """
        Once it has been determined that the input is invalid, we should
        tell our view to report this fact to the user.
        """
        self._parent.aggregateInvalid(request, self, data)
        self.view.setError(request, self.invalidErrorText)

    def aggregateInvalid(self, request, inputhandler, data):
        """By default we just pass this method call all the way up to the root
        Controller.
        """
        self._parent.aggregateInvalid(request, inputhandler, data)

    def commit(self, request, node, data):
        """
        It has been determined that the input for the entire form is completely
        valid; it is now safe for all handlers to commit changes to the model.
        """
        if self._commit is None:
            data = str(data)
            if data != self.view.getData():
                self.model.setData(data)
                self.model.notify({'request': request, self.submodel: data})
        else:
            func = self._commit
            if hasattr(func, 'im_func'):
                func = func.im_func
            args, varargs, varkw, defaults = inspect.getargspec(func)
            if args[1] == 'request':
                self._commit(request, data)
            else:
                self._commit(data)


class DefaultHandler(InputHandler):
    def handle(self, request):
        """
        By default, we don't do anything
        """
        pass


class SingleValue(InputHandler):
    def getInput(self, request):
        name = getattr(self, 'inputName', self.submodel)
        input = request.args.get(name, None)
        if input:
            return input[0]


class Anything(SingleValue):
    """
    Handle anything except for None
    """
    def check(self, request, data):
        if data is not None:
            return 1
        return None


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
        self.invalidErrorText = "%s is not an integer. Please enter an integer." % data
        SingleValue.handleInvalid(self, request, data)


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
        self.invalidErrorText = "%s is not an float. Please enter a float." % data
        SingleValue.handleInvalid(self, request, data)


class List(InputHandler):
    def check(self, request, data):
        return None


class DictAggregator(Anything):
    """An InputHandler for a <form> tag, for triggering a function
    when all of the form's individual inputs have been validated.
    Also for use gathering a dict of arguments to pass to a parent's
    aggregateValid if no commit function is passed.
    
    Usage example::
        <form controller="theForm" action="">
            <input controller="Integer" 
                view="InputText" model="anInteger" />
            <input controller="Anything" 
                view="InputText" model="aString" />
            <input type="submit" />
        </form>
        
        def theCommitFunction(anInteger=None, aString=None):
            '''Note how the keyword arguments match up with the leaf model
            names above
            '''
            print "Yay", anInteger, aString
        
        class CMyController(controller.Controller):
            def wcfactory_theForm(self, request, node, m):
                return input.FormAggregator(m, commit=theCommitFunction)
    """
    def aggregateValid(self, request, inputhandler, data):
        """Aggregate valid input from inputhandlers below us, into a dictionary.
        """
        self._valid[inputhandler] = data

    def aggregateInvalid(self, request, inputhandler, data):
        self._invalid[inputhandler] = data

    def exit(self, request):
        """This is the node complete message
        """
        if self._commit:
            # Introspect the commit function to see what 
            # keyword arguments it takes
            func = self._commit
            if hasattr(func, 'im_func'):
                func = func.im_func
            args, varargs, varkw, defaults = inspect.getargspec(
                func)
            wantsRequest = len(args) > 1 and args[1] == 'request'

        if self._invalid:
            # whoops error!!!1
            if self._errback:
                self._errback(request, self._invalid)
        elif self._valid:
            # We've got all the input
            # Gather it into a dict and call the commit function
            results = {}
            for item in self._valid:
                results[item.model.name] = self._valid[item]
            if self._commit:
                if wantsRequest:
                    self._commit(request, **results)
                else:
                    self._commit(**results)
            else:
                self._parent.aggregateValid(request, self, results)
            return results


class ListAggregator(Anything):
    def aggregateValid(self, request, inputhandler, data):
        """Aggregate valid input from inputhandlers below us into a 
        list until we have all input from controllers below us to pass 
        to the commit function that was passed to the constructor or
        our parent's aggregateValid.
        """
        if not hasattr(self, '_validList'):
            self._validList = []
        self._validList.append(data)

    def aggregateInvalid(self, request, inputhandler, data):
        if not hasattr(self, '_invalidList'):
            self._invalidList = []
        self._invalidList.append(data)

    def exit(self, request):
        if self._commit:
            # Introspect the commit function to see what 
            #arguments it takes
            func = self._commit
            if hasattr(func, 'im_func'):
                func = func.im_func
            args, varargs, varkw, defaults = inspect.getargspec(func)
            self.numArgs = len(args)
            wantsRequest = args[1] == 'request'
            if wantsRequest:
                numArgs -= 1
        else:
            # Introspect the template to see if we still have
            # controllers that will be giving us input
            
            # aggregateValid is called before the view renders the node, so
            # we can count the number of controllers below us the first time
            # we are called
            if not hasattr(self, 'numArgs'):
                self.numArgs = len(domhelpers.findElementsWithAttributeShallow(
                    self.view.node, "controller"))

        if self._invalidList:
            self._parent.aggregateInvalid(request, self, self._invalidList)
        else:
            if self._commit:
                if wantsRequest:
                    self._commit(request, *self._validList)
                else:
                    self._commit(*self._validList)
            self._parent.aggregateValid(request, self, self._invalidList)
        
    def commit(self, request, node, data):
        """If we're using the ListAggregator, we don't want the list of items
        to be rerendered
        xxx Need to have a "node complete" message sent to the controller
        so we can reset state, so controllers can be re-run or ignore input the second time
        """
        pass

