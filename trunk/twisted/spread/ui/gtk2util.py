# Copyright (c) Twisted Matrix Laboratories.
# See LICENSE for details.

import gtk

from twisted import copyright
from twisted.internet import defer
from twisted.python import failure, log, util
from twisted.spread import pb
from twisted.cred.credentials import UsernamePassword

from twisted.internet import error as netError

def login(client=None, **defaults):
    """
    @param host:
    @param port:
    @param identityName:
    @param password:
    @param serviceName:
    @param perspectiveName:

    @returntype: Deferred RemoteReference of Perspective
    """
    d = defer.Deferred()
    LoginDialog(client, d, defaults)
    return d

class GladeKeeper:
    """
    @cvar gladefile: The file in which the glade GUI definition is kept.
    @type gladefile: str

    @cvar _widgets: Widgets that should be attached to me as attributes.
    @type _widgets: list of strings
    """

    gladefile = None
    _widgets = ()

    def __init__(self):
        from gtk import glade
        self.glade = glade.XML(self.gladefile)

        # mold can go away when we get a newer pygtk (post 1.99.14)
        mold = {}
        for k in dir(self):
            mold[k] = getattr(self, k)
        self.glade.signal_autoconnect(mold)
        self._setWidgets()

    def _setWidgets(self):
        get_widget = self.glade.get_widget
        for widgetName in self._widgets:
            setattr(self, "_" + widgetName, get_widget(widgetName))


class LoginDialog(GladeKeeper):
    # IdentityConnector host port identityName password
    # requestLogin -> identityWrapper or login failure
    # requestService serviceName perspectiveName client

    # window killed
    # cancel button pressed
    # login button activated

    fields = ['host','port','identityName','password',
              'perspectiveName']

    _widgets = ("hostEntry", "portEntry", "identityNameEntry", "passwordEntry",
                "perspectiveNameEntry", "statusBar",
                "loginDialog")

    _advancedControls = ['perspectiveLabel', 'perspectiveNameEntry',
                         'protocolLabel', 'versionLabel']

    gladefile = util.sibpath(__file__, "login2.glade")

    _timeoutID = None

    def __init__(self, client, deferred, defaults):
        self.client = client
        self.deferredResult = deferred

        GladeKeeper.__init__(self)

        self.setDefaults(defaults)
        self._loginDialog.show()


    def setDefaults(self, defaults):
        if not defaults.has_key('port'):
            defaults['port'] = str(pb.portno)
        elif isinstance(defaults['port'], (int, long)):
            defaults['port'] = str(defaults['port'])

        for k, v in defaults.iteritems():
            if k in self.fields:
                widget = getattr(self, "_%sEntry" % (k,))
                widget.set_text(v)

    def _setWidgets(self):
        GladeKeeper._setWidgets(self)
        self._statusContext = self._statusBar.get_context_id("Login dialog.")
        get_widget = self.glade.get_widget
        get_widget("versionLabel").set_text(copyright.longversion)
        get_widget("protocolLabel").set_text("Protocol PB-%s" %
                                             (pb.Broker.version,))

    def _on_loginDialog_response(self, widget, response):
        handlers = {gtk.RESPONSE_NONE: self._windowClosed,
                   gtk.RESPONSE_DELETE_EVENT: self._windowClosed,
                   gtk.RESPONSE_OK: self._doLogin,
                   gtk.RESPONSE_CANCEL: self._cancelled}
        handler = handlers.get(response)
        if handler is not None:
            handler()
        else:
            log.msg("Unexpected dialog response %r from %s" % (response,
                                                               widget))

    def _on_loginDialog_close(self, widget, userdata=None):
        self._windowClosed()

    def _on_loginDialog_destroy_event(self, widget, userdata=None):
        self._windowClosed()

    def _cancelled(self):
        if not self.deferredResult.called:
            self.deferredResult.errback(netError.UserError("User hit Cancel."))
        self._loginDialog.destroy()

    def _windowClosed(self, reason=None):
        if not self.deferredResult.called:
            self.deferredResult.errback(netError.UserError("Window closed."))

    def _doLogin(self):
        idParams = {}

        idParams['host'] = self._hostEntry.get_text()
        idParams['port'] = self._portEntry.get_text()
        idParams['identityName'] = self._identityNameEntry.get_text()
        idParams['password'] = self._passwordEntry.get_text()

        try:
            idParams['port'] = int(idParams['port'])
        except ValueError:
            pass

        f = pb.PBClientFactory()
        from twisted.internet import reactor
        reactor.connectTCP(idParams['host'], idParams['port'], f)
        creds = UsernamePassword(idParams['identityName'], idParams['password'])
        d = f.login(creds, self.client)
        def _timeoutLogin():
            self._timeoutID = None
            d.errback(failure.Failure(defer.TimeoutError("Login timed out.")))
        self._timeoutID = reactor.callLater(30, _timeoutLogin)
        d.addCallbacks(self._cbGotPerspective, self._ebFailedLogin)
        self.statusMsg("Contacting server...")

        # serviceName = self._serviceNameEntry.get_text()
        # perspectiveName = self._perspectiveNameEntry.get_text()
        # if not perspectiveName:
        #     perspectiveName = idParams['identityName']

        # d = _identityConnector.requestService(serviceName, perspectiveName,
        #                                       self.client)
        # d.addCallbacks(self._cbGotPerspective, self._ebFailedLogin)
        # setCursor to waiting

    def _cbGotPerspective(self, perspective):
        self.statusMsg("Connected to server.")
        if self._timeoutID is not None:
            self._timeoutID.cancel()
            self._timeoutID = None
        self.deferredResult.callback(perspective)
        # clear waiting cursor
        self._loginDialog.destroy()

    def _ebFailedLogin(self, reason):
        if isinstance(reason, failure.Failure):
            reason = reason.value
        self.statusMsg(reason)
        if isinstance(reason, (unicode, str)):
            text = reason
        else:
            text = unicode(reason)
        msg = gtk.MessageDialog(self._loginDialog,
                                gtk.DIALOG_DESTROY_WITH_PARENT,
                                gtk.MESSAGE_ERROR,
                                gtk.BUTTONS_CLOSE,
                                text)
        msg.show_all()
        msg.connect("response", lambda *a: msg.destroy())

        # hostname not found
        # host unreachable
        # connection refused
        # authentication failed
        # no such service
        # no such perspective
        # internal server error

    def _on_advancedButton_toggled(self, widget, userdata=None):
        active = widget.get_active()
        if active:
            op = "show"
        else:
            op = "hide"
        for widgetName in self._advancedControls:
            widget = self.glade.get_widget(widgetName)
            getattr(widget, op)()

    def statusMsg(self, text):
        if not isinstance(text, (unicode, str)):
            text = unicode(text)
        return self._statusBar.push(self._statusContext, text)
