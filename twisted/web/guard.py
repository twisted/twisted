# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.


"""DEPRECATED.

You probably should be using twisted.web.woven.guard instead.
"""

# System Imports
import string, traceback
from cStringIO import StringIO

from twisted.python import log

# Sibling Imports
import error
import html
import resource
import widgets
from server import NOT_DONE_YET

import warnings
warnings.warn("Please use twisted.web.woven.guard", DeprecationWarning, 2)


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


class AuthForm(widgets.Form):
    formFields = [
        ['string','Identity','username',''],
        ['password','Password','password',''],
        ['string','Perspective','perspective','']
        ]

    formAcceptExtraArgs = 1
    
    def __init__(self, reqauth, sessionIdentity=None, sessionPerspective=None):
        """Initialize, specifying various options.
        
        @param reqauth: a web.resource.Resource instance, indicating which
              resource a user will be logging into with this form; this must
              specify a serviceName attribute which indicates the name of the
              service from which perspectives will be requested.

        @param sessionIdentity: if specified, the name of the attribute on
              the user's session to set for the identity they get from logging
              in to this form.
            
        @param sessionPerspective: if specified, the name of the attribute on
              the user's session to set for the perspective they get from
              logging in to this form.
        """
        self.reqauth = reqauth
        self.sessionPerspective = sessionPerspective
        self.sessionIdentity = sessionIdentity

    def gotPerspective(self, perspective, request, ident):
        # TODO: fix this...
        resKey = string.join(['AUTH',self.reqauth.service.serviceName], '_')
        sess = request.getSession()
        setattr(sess, resKey, perspective)
        if self.sessionPerspective:
            setattr(sess, self.sessionPerspective, perspective)
            if self.sessionIdentity:
                setattr(sess, self.sessionIdentity, ident)
            p = perspective.attached(sess, ident)
            _Detacher(sess, ident, p)
        return self.reqauth.reallyRender(request)
    
    def didntGetPerspective(self, error, request):
        log.msg('Password not verified! Error: %s' % error)
        io = StringIO()
        io.write(self.formatError("Login incorrect."))
        self.format(self.getFormFields(request), io.write, request)
        return [io.getvalue()]

    def gotIdentity(self, ident, password, request, perspectiveName):
        pwrq = ident.verifyPlainPassword(password)
        pwrq.addCallback(self.passwordIsOk, ident, password,
                         request, perspectiveName)
        pwrq.addErrback(self.didntGetPerspective, request)
        pwrq.needsHeader = 1
        return [pwrq]

    def passwordIsOk(self, msg, ident, password, request, perspectiveName):
        ret = ident.requestPerspectiveForKey(self.reqauth.service.serviceName,
                                             perspectiveName).addCallbacks(
            self.gotPerspective, self.didntGetPerspective,
            callbackArgs=(request,ident),
            errbackArgs=(request,))
        ret.needsHeader = 1
        return [ret]

    def didntGetIdentity(self, unauth, request):
        io = StringIO()
        io.write(self.formatError("Login incorrect."))
        self.format(self.getFormFields(request), io.write, request)
        return io.getvalue()

    def process(self, write, request, submit, username, password, perspective):
        """Process the form results.
        """
        # must be done before page is displayed so cookie can get set!
        request.getSession()
        # this site must be tagged with an application.
        idrq = self.reqauth.service.authorizer.getIdentityRequest(username)
        idrq.needsHeader = 1
        idrq.addCallbacks(self.gotIdentity, self.didntGetIdentity,
                          callbackArgs=(password,request,perspective or username),
                          errbackArgs=(request,))
        return [idrq]

class AuthPage(widgets.Page):
    template = '''
    <html><head><title>Authorization Required</title></head>
    <body>
    <center>
    %%%%authForm%%%%
    </center>
    </body>
    </html>
    '''
    authForm = None
    def __init__(self, reqauth, sessionIdentity=None, sessionPerspective=None):
        widgets.Page.__init__(self)
        self.authForm = AuthForm(reqauth, sessionPerspective, sessionIdentity)


class WidgetGuard(widgets.Widget):
    
    def __init__(self, wid, service,
                 sessionIdentity=None,
                 sessionPerspective=None):
        self.wid = wid
        self.service = service
        self.sessionPerspective = sessionPerspective
        self.sessionIdentity = sessionIdentity

    def reallyRender(self, request):
        return widgets.possiblyDeferWidget(self.wid, request)

    def display(self, request):
        session = request.getSession()
        resKey = string.join(['AUTH',self.service.serviceName], '_')
        if hasattr(session, resKey):
            return self.wid.display(request)
        else:
            return AuthForm(self).display(request)



# TODO hiding forms behind a ResourceGuard sucks, because if
# ResourceGuard needs to authenticate the user, it will 1) complain
# about the form submitted, 2) throw the data away. This happens if
# you use "foo?a=b" -style URLs and the user hasn't authenticated yet,
# or with session expiry.

class ResourceGuard(resource.Resource):

    isLeaf = 1

    def __init__(self, res, service, sessionIdentity=None, sessionPerspective=None):
        resource.Resource.__init__(self)
        self.res = res
        self.service = service
        self.sessionPerspective = sessionPerspective
        self.sessionIdentity = sessionIdentity

    def __getattr__(self, k):
        if not self.__dict__.has_key("res"):
            raise AttributeError, k
        return getattr(self.res, k)

    def __getstate__(self):
        return self.__dict__.copy()
    
    def listNames(self):
        return self.res.listNames()
    
    def reallyRender(self, request):
        # it's authenticated already...
        res = resource.getChildForRequest(self.res, request)
        val = res.render(request)
        if val != NOT_DONE_YET:
            request.write(val)
            request.finish()
        return widgets.FORGET_IT

    def render(self, request):
        session = request.getSession()
        resKey = string.join(['AUTH',self.service.serviceName], '_')
        if hasattr(session, resKey):
            self.reallyRender(request)
            return NOT_DONE_YET
        else:
            return AuthPage(self,
                            self.sessionPerspective,
                            self.sessionIdentity).render(request)

