
# Sibling Imports
import widgets

def requestSessionPerspective(session, serviceName):
    if hasattr(session, 'identity'):
        for serviceN, perspectiveN in session.identity.getAllKeys():
            if serviceN == serviceName:
                return session.identity.requestPerspectiveForKey(serviceN, perspectiveN)
    return defer.fail("Unauthorized") # TODO: link to login form?


class _Detacher:
    """Detach a web session from an attached perspective.

    This will happen when the session expires.
    """
    
    def __init__(self, session, identity, perspective):
        self.session = session
        self.identity = identity
        self.perspective = perspective
        session.notifyOnExpire(self.detach)
    
    def detach(self):
        self.perspective.detached(self.session, self.identity)
        del self.session
        del self.identity
        del self.perspective


class SessionPerspectiveMixin(widgets.WidgetMixin):
    """I mix in the functionality of adding a Perspective to the request's session.

    In order to retrieve the perspective, call self.getPerspective(request).
    """
    
    def __init__(self, service):
        """Initialize me with a service.

        This service is used to determine where the perspective that will be
        attached to the session will come from.  If an identity has multiple
        perspectives with that service, the first one (in alphabetical order)
        will be used.
        """
        self.service = service

    def gotPerspective(self, resultPerspective, request):
        sess = request.getSession()
        resultPerspective.attached(sess,sess.identity)
        _Detacher(sess, sess.identity, resultPerspective)
        sess.perspectives[self.service.serviceName] = resultPerspective
        return self.displayMixedWidget(request)

    def display(self, request):
        """See widgets.WidgetMixin.
        """
        sess = request.getSession()
        print 'I bet we NEVER SEE THIS', sess
        if hasattr(sess,'perspectives'):
            if sess.perspectives.has_key(self.service.serviceName):
                return self.displayMixedWidget(request)
            else:
                return [sess.identity.requestPerspectiveForService(self.service.serviceName)\
                        .addCallback(self.gotPerspective,request)]
        else:
            return self.displayMixedWidget(request)
                                                              
    def getPerspective(self, request):
        """Return a Perspective instance.
        """
        sess = request.getSession()
        print 'in getPerspective', sess
        if hasattr(sess, 'perspectives'):
            return sess.perspectives.get(self.service.serviceName)

class LogInForm(widgets.Form):
    formFields = [
        ['string','Identity','identityName',''],
        ['password','Password','password','']
        ]

    def process(self, write, request, submit, identityName, password):
        """Process the form results.
        """
        # must be done before page is displayed so cookie can get set!
        request.getSession()
        # this site must be tagged with an application.
        idrq = request.site.app.authorizer.getIdentityRequest(identityName)
        idrq.needsHeader = 1
        idrq.addCallbacks(self.gotIdentity, self.didntGetIdentity,
                          callbackArgs=(password, request),
                          errbackArgs=(request,))
        return [idrq]

    def gotIdentity(self, ident, password, request):
        if ident.verifyPlainPassword(password):
            session = request.getSession()
            session.identity = ident
            session.perspectives = {}
            return ["OKAY OKAY!"]
        else:
            return self.didntGetPerspective("no such identity", request)

    def didntGetIdentity(self, unauth, request):
        io = StringIO()
        io.write(self.formatError("Login incorrect."))
        self.format(self.getFormFields(request), io.write, request)
        return io.getvalue()

