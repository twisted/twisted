# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
# 
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
# 
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

# Sibling Imports
import widgets
from twisted.python import failure

from cStringIO import StringIO

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

    def _cbPerspective(self, resultPerspective, request):
        sess = request.getSession()
        resultPerspective.attached(sess,sess.identity)
        _Detacher(sess, sess.identity, resultPerspective)
        sess.perspectives[self.service.serviceName] = resultPerspective
        return self.displayMixedWidget(request)

    def _ebPerspective(self, fail, request):
        return self.displayMixedWidget(request)

    def display(self, request):
        """See widgets.WidgetMixin.
        """
        sess = request.getSession()
        if hasattr(sess,'perspectives'):
            if sess.perspectives.has_key(self.service.serviceName):
                return self.displayMixedWidget(request)
            else:
                return [sess.identity.requestPerspectiveForService(self.service.serviceName)\
                        .addCallbacks(self._cbPerspective,self._ebPerspective,
                                      callbackArgs=(request,),errbackArgs=(request,))]
        else:
            return self.displayMixedWidget(request)
                                                              
    def getPerspective(self, request):
        """Return a Perspective instance.
        """
        sess = request.getSession()
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
        idrq.addCallbacks(self._cbIdentity, self._ebIdentity,
                          callbackArgs=(identityName, password, request),
                          errbackArgs=(request,))
        return [idrq]

    def _cbIdentity(self, ident, identityName, password, request):
        pwrq = ident.verifyPlainPassword(password)
        pwrq.addCallback(self._passwordIsOk, ident, identityName, request)
        pwrq.addErrback(self._passwordIsBad, request)
        return [pwrq]

    def _passwordIsOk(self, msg, ident, identityName, request):
        session = request.getSession()
        session.identity = ident
        session.perspectives = {}
        r = ["Logged in as %s: %s" % repr(identityName, msg)]
        w = r.append
        self.format(self.getFormFields(request), w, request)
        return r

    def _passwordIsBad(self, error):
        self._ebIdentity(failure.Failure(KeyError("Invalid login.")), request)
    
    def _ebIdentity(self, fail, request):
        fail.trap(KeyError)
        l = []
        w = l.append
        w(self.formatError(fail.getErrorMessage()))
        self.format(self.getFormFields(request), w, request)
        return l

