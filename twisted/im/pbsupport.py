
from libglade import GladeXML

from twisted.spread import pb

from twisted.im.locals import GLADE_FILE, autoConnectMethods, ONLINE, OFFLINE, AWAY
from twisted.im.chat import getContactsList, getGroup, getGroupConversation, getPerson, getConversation


### --- Twisted.Words Account stuff.

class TwistedWordsPerson:
    """Abstract represntation of a person I can talk to on t.w
    """
    def __init__(self, name, wordsClient):
        self.name = name                # what's my name
        self.status = OFFLINE                 # am I online
        self.account = wordsClient      # object through which I communicate

    def isOnline(self):
        return ((self.status == ONLINE) or
                (self.status == AWAY))

    def getStatus(self):
        return ((self.status == ONLINE) and "Online" or
                "Away")

    def sendMessage(self, text):
        """Return a deferred...
        """
        return self.account.perspective.directMessage(self.name, text)

    def setStatus(self, status):
        self.status = status
        getContactsList().setContactStatus(self)

class TwistedWordsGroup:
    def __init__(self, name, wordsClient):
        self.name = name
        self.account = wordsClient
        self.joined = 0

    def sendGroupMessage(self, text):
        """Return a deferred.
        """
        return self.account.perspective.groupMessage(self.name, text)

    def joining(self):
        self.joined = 1

    def leaving(self):
        self.joined = 0

    def leave(self):
        return self.account.perspective.leaveGroup(self.name)



class TwistedWordsClient(pb.Referenceable):
    """In some cases, this acts as an Account, since it a source of text
    messages (multiple Words instances may be on a single PB connection)
    """
    def __init__(self, acct, serviceName, perspectiveName):
        self.accountName = "%s (%s:%s)" % (acct.accountName, serviceName, perspectiveName)
        self.name = perspectiveName
        print "HELLO I AM A PB SERVICE", serviceName, perspectiveName

    def getGroup(self, name):
        return getGroup(name, self, TwistedWordsGroup)

    def getGroupConversation(self, name):
        return getGroupConversation(self.getGroup(name))

    def remote_receiveGroupMembers(self, names, group):
        print 'received group members:', names, group
        self.getGroupConversation(group).setGroupMembers(names)

    def remote_receiveGroupMessage(self, sender, group, message):
        print 'received a group message', sender, group, message
        self.getGroupConversation(group).showGroupMessage(sender, message)

    def remote_memberJoined(self, member, group):
        print 'member joined', member, group
        self.getGroupConversation(group).memberJoined(member)

    def remote_memberLeft(self, member, group):
        print 'member left'
        self.getGroupConversation(group).memberLeft(member)

    def remote_notifyStatusChanged(self, name, status):
        getPerson(name, self, TwistedWordsPerson).setStatus(status)

    def remote_receiveDirectMessage(self, name, message):
        getConversation(getPerson(name, self, TwistedWordsPerson)).showMessage(message)

    def remote_receiveContactList(self, clist):
        for name, status in clist:
            getPerson(name, self, TwistedWordsPerson).setStatus(status)

    def joinGroup(self, name):
        self.getGroup(name).joining()
        return self.perspective.joinGroup(name).addCallback(self._cbGroupJoined, name)

    def leaveGroup(self, name):
        self.getGroup(name).leaving()
        return self.perspective.leaveGroup(name).addCallback(self._cbGroupLeft, name)

    def _cbGroupJoined(self, result, name):
        groupConv = getGroupConversation(self.getGroup(name))
        groupConv.showGroupMessage("sys", "you joined")
        self.perspective.getGroupMembers(name)

    def _cbGroupLeft(self, result, name):
        print 'left',name
        groupConv = getGroupConversation(self.getGroup(name), 1)
        groupConv.showGroupMessage("sys", "you left")

    def connected(self, perspective):
        print 'Connected Words Client!', perspective
        registerAccount(self)
        self.perspective = perspective
        getContactsList()



pbGtkFrontEnds = {
    "twisted.words": TwistedWordsClient, 
    "twisted.reality": None
    }


class PBAccount:
    isOnline = 0
    gatewayType = "PB"
    def __init__(self, accountName, autoLogin,
                 host, port, identity, password, services):
        self.accountName = accountName
        self.autoLogin = autoLogin
        self.password = password
        self.host = host
        self.port = port
        self.identity = identity
        self.services = []
        for serviceType, serviceName, perspectiveName in services:
            self.services.append([pbGtkFrontEnds[serviceType], serviceName,
                                  perspectiveName])

    def logOn(self):
        print 'Connecting...',
        pb.getObjectAt(self.host, self.port).addCallbacks(self._cbConnected,
                                                          self._ebConnected)

    def _cbConnected(self, root):
        print 'Connected!'
        print 'Identifying...',
        pb.authIdentity(root, self.identity, self.password).addCallbacks(
            self._cbIdent, self._ebConnected)

    def _cbIdent(self, ident):
        print 'Identified!'
        for handlerClass, sname, pname in self.services:
            handler = handlerClass(self, sname, pname)
            ident.attach(sname, pname, handler).addCallback(handler.connected)

    def _ebConnected(self, error):
        print 'Not connected.'
        return error

class PBAccountForm:
    def __init__(self, manager):
        self.manager = manager
        self.xml = GladeXML(GLADE_FILE, root="PBAccountWidget")
        autoConnectMethods(self)
        self.widget = self.xml.get_widget("PBAccountWidget")
        self.on_serviceType_changed()
        self.selectedRow = None

    def addPerspective(self, b):
        stype = self.xml.get_widget("serviceType").get_text()
        sname = self.xml.get_widget("serviceName").get_text()
        pname = self.xml.get_widget("perspectiveName").get_text()
        self.xml.get_widget("serviceList").append([stype, sname, pname])

    def removePerspective(self, b):
        if self.selectedRow is not None:
            self.xml.get_widget("serviceList").remove(self.selectedRow)

    def on_serviceType_changed(self, w=None):
        self.xml.get_widget("serviceName").set_text(self.xml.get_widget("serviceType").get_text())
        self.xml.get_widget("perspectiveName").set_text(self.xml.get_widget("identity").get_text())

    on_identity_changed = on_serviceType_changed

    def on_serviceList_select_row(self, slist, row, column, event):
        self.selectedRow = row

    def create(self, accName, autoLogin):
        host = self.xml.get_widget("hostname").get_text()
        port = self.xml.get_widget("portno").get_text()
        user = self.xml.get_widget("identity").get_text()
        pasw = self.xml.get_widget("password").get_text()
        serviceList = self.xml.get_widget("serviceList")
        services = []
        for r in xrange(0, serviceList.rows):
            row = []
            for c in xrange(0, serviceList.columns):
                row.append(serviceList.get_text(r, c))
            services.append(row)
        if not services:
            services.append([
                self.xml.get_widget("serviceType").get_text(),
                self.xml.get_widget("serviceName").get_text(),
                self.xml.get_widget("perspectiveName").get_text()])
        return PBAccount(accName, autoLogin, host, int(port), user, pasw, services)





from twisted.im.account import registerAccount
