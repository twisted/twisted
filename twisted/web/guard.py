
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

# System Imports
import string, traceback
from cStringIO import StringIO

# Twisted Imports
from twisted.internet import passport

# Sibling Imports
import error
import html
import resource
import widgets
from server import NOT_DONE_YET


class AuthForm(widgets.Form):
    formFields = [
        ['string','Identity','username',''],
        ['password','Password','password',''],
        ['string','Perspective','perspective','']
        ]

    def __init__(self, reqauth):
        self.reqauth = reqauth

    def gotIdentity(self, ident, password, request, perspectiveName):
        if ident.verifyPlainPassword(password):
            try:
                perspective = ident.getPerspectiveForKey(self.reqauth.serviceName, perspectiveName)
            except KeyError:
                traceback.print_exc()
            else:
                resKey = string.join(['AUTH',self.reqauth.serviceName]+request.prepath, '_')
                setattr(request.getSession(), resKey, perspective)
                return self.reqauth.reallyRender(request)
        else:
            print 'password not verified'
        # TODO: render the form as if an exception were thrown from the
        # data processing step...
        return "beep"

    def didntGetIdentity(self, unauth, request):
        return "beep"

    def process(self, write, request, username, password, perspective):
        """Process the form results.
        """
        # must be done before page is displayed so cookie can get set!
        request.getSession()
        # this site must be tagged with an application.
        idrq = request.site.app.authorizer.getIdentityRequest(username)
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
    def __init__(self, reqauth):
        widgets.Page.__init__(self)
        self.authForm = AuthForm(reqauth)


class WidgetGuard(widgets.Widget):
    def __init__(self, wid, serviceName):
        self.wid = wid
        self.serviceName = serviceName

    def reallyRender(self, request):
        return widgets.possiblyDeferWidget(self.wid, request)

    def display(self, request):
        session = request.getSession()
        resKey = string.join(['AUTH',self.serviceName]+request.prepath, '_')
        if hasattr(session, resKey):
            return self.wid.display(request)
        else:
            return AuthForm(self).display(request)

    

class ResourceGuard(resource.Resource):
    isLeaf = 1
    def __init__(self, res, serviceName):
        self.res = res
        self.serviceName = serviceName

    def reallyRender(self, request):
        # it's authenticated already...
        try:
            res = self.res.getChildForRequest(request)
            val = res.render(request)
            if val != NOT_DONE_YET:
                request.write(val)
                request.finish()
        except:
            io = StringIO()
            traceback.print_exc(file=io)
            request.write(html.PRE(io.getvalue()))
            request.finish()
        return widgets.FORGET_IT

    def render(self, request):
        session = request.getSession()
        resKey = string.join(['AUTH',self.serviceName]+request.prepath, '_')
        if hasattr(session, resKey):
            self.reallyRender(request)
            return NOT_DONE_YET
        else:
            return AuthPage(self).render(request)

