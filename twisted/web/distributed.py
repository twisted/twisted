"""I hold classes that deal with distributed twisted.web servers.
"""
#t.w imports
import server
import resource
import html
import static
import error

from twisted.protocols import http
from twisted import gloop
from twisted import log
from twisted.python import authenticator

import cPickle

class ResourceSubscription(resource.Resource):
    """I am a resource which represents a remote Twisted Web server.

    You can create servers (ResourcePublishers) which publish a resource not to
    HTTP, but a custom proxy protocol which twisted web uses to communicate
    with itself.  This is to be used, for example, if you have a webserver
    which has multiple users, each with arbitrary executable content, such as
    CGI scripts or webserver-internal Python code (custom resources or EPY
    files).

    This does have the overhead of one persistent process per user, but the
    philosophical benefits in security that this grants are worth it.
    Resource-control is more feasible, the main webserver does not need to run
    as root, etcetera.

    """
    isLeaf = 1
    gloopClient = None
    def __init__(self, host,port):
        """Initialize with a host and a port to connect to.
        """
        self.reshost = host
        self.resport = port
        self.pendingIssues = []
        self.gloopClientConnect(sel)
        resource.Resource.__init__(self)

    def __getstate__(self):
        """(internal) Serialize.

        Never serialize pending issues or my gloop client.
        """
        x = copy.copy(self.__dict__)
        if x.has_key('gloopClient'):
            del x['gloopClient']
        if x.has_key('pendingIssues'):
            x['pendingIssues'] = []
        return x

    def gloopClientConnect(self, selector):
        """Reconnect my gloop client.
        """
        print "ResourceSubscription attempting to reconnect (%s, %s)" %(self.reshost, self.resport)
        self.gloopClient = ResourcePublisherClient('web','web')
        self.gloopClient.subscription = self
        transport = net.TCPClient(self.reshost, self.resport, self.gloopClient, selector)

    def processPendingIssues(self):
        """Process all pending subscription issues.

        Since the connection is lazily initiated (e.g. initiated whenever a
        request occurrs), there are some requests which cannot be resolved when
        they are made; they must be resolved when the request is initiated.
        This processes them when the connection is made.
        """
        for issue in self.pendingIssues:
            issue.requestIssue(self)
        self.pendingIssues = []

    def ignorePendingIssues(self):
        """Ignore (issue an error for) all pending subscription issues
        """
        for issue in self.pendingIssues:
            issue.ignoreIssue(self)
        self.pendingIssues = []

    def render(self, request):
        """Render this request, from my server.

        This will always be asynchronous, and therefore return NOT_DONE_YET.
        It spins off a request to the gloop client, and either adds it to the
        list of pending issues or requests it immediately, depending on if the
        client is already connected.
        """
        if not self.gloopClient:
            self.gloopClientConnect(
                request.transport.server.selector)

        ri = ResourceIssue(request)
        if self.gloopClient.connected:
            ri.requestIssue(self)
        else:
            self.pendingIssues.append(ri)
        return server.NOT_DONE_YET

class ResourceIssue:
    """(internal) I am an issue of a subscription.

    An 'issue' is a response to one distributed web-request.
    """
    def __init__(self, request):
        """Initialize with a given request.

        Remove various attributes from the request, serialize it, and store
        both it and the serialized representation.
        """
        prq = copy.copy(request)
        del prq.transport
        del prq.server
        del prq.selector
        self.pickledRequest = cPickle.dumps(prq)
        self.request = request

    def requestIssue(self, resourceSubscription):
        """Send the request over the wire.

        This sends the serialized state of the request over the wire, along
        with a backreference to the actual request, and callbacks to make when
        the request completes.
        """
        resourceSubscription.gloopClient.pageRequest(
            self.pickledRequest, self.request,
            callback = self.doneWithOutput,
            errback = self.doneWithError)

    def ignoreIssue(self, resourceSubscription):
        """Ignore this issue because the server was unable to connect.

        Print an informative message.
        """
        self.doneWithError("Unable To Connect.")

    def doneWithOutput(self, output):
        """The response finished with some return value; I'm done.

        If the response finished with the canonical NOT_DONE_YET value, then
        I'm finished.
        """
        if output != server.NOT_DONE_YET:
            self.request.write(output)
            self.request.finish()

    def doneWithError(self, errorInfo):
        """A remote method call caused a traceback.  Die.

        This should display the on the webpage and close
        the connection.
        """
        if hasattr(errorInfo, 'traceback'):
            tbInfo = errorInfo.traceback
        else:
            tbInfo = "No traceback."

        self.doneWithOutput(
            error.ErrorPage(http.INTERNAL_SERVER_ERROR,
                      "Server Connection Lost",
                      "Connection to distributed server lost:" +
                      html.PRE(tbInfo)).
            render(self.request))


class ResourcePublisherClient(gloop.ClientProtocol, log.Logger):
    """(internal) I am a client for distributed resources.

    This is ephemeral state used by ResourceSubscription to maintain a
    connection to its server.
    """
    connected = 0

    def localSetup(self):
        """Setup local state.
        """
        self.connected = 1

    def remoteSetup(self):
        """Set up remote state.

        Process all pending issues (ones requested before the connection was
        made)
        """
        self.pageRequest = self['handlePageRequest']
        self.subscription.processPendingIssues()

    def connectionLost(self):
        """The connection has been lost.

        Display a log message and clean up.
        """
        print 'losing ipc connection',self
        gloop.ClientProtocol.connectionLost(self)
        self.subscription.ignorePendingIssues()
        self.pageRequest = None
        del self.subscription.gloopClient
        connected = 0

class ResourcePublish(gloop.ServerProtocol):
    def handlePageRequest(self, pickledRequest, remoteRequest):
        rq = cPickle.loads(pickledRequest)
        # Grab the "post" path -- I.E. the parsed-out portion of the
        # remainder of the path, and assume that's the root for this
        # server.
        resrc = self.server.root
        rq.write = remoteRequest.write
        rq.finish = remoteRequest.finish
        rq.registerProducer = remoteRequest.registerProducer
        rq.setResponseCode = remoteRequest.setResponseCode
        rq.setHeader = remoteRequest.setHeader
        rq.selector = self.server.selector
        rq.server = self.server
        print 'remote',rq
        while rq.postpath and not resrc.isLeaf:
            pathElement = rq.postpath.pop(0)
            rq.prepath.append(pathElement)
            resrc = resrc.getChildWithDefault(pathElement, rq)
        return resrc.render(rq)

    def localSetup(self):
        self.addName('handlePageRequest', self.handlePageRequest)

    def remoteSetup(self):
        pass

class ResourcePublisher(gloop.Server, authenticator.SessionManager):
    protocol = ResourcePublish
    authenticator = authenticator.Authenticator()
    authenticator.addUser('web','web')
    def __init__(self, *args, **kw):
        apply(gloop.Server.__init__, (self,)+args, kw)
        authenticator.SessionManager.__init__(self)
    def setRoot(self, root):
        self.root = root
        root.server = self


class UserDirectory(html.Interface):
    userDirName = 'public_html'
    userSocketName = '.twistd-web-service'

    def listUsers(self, req):
        import pwd
        x = StringIO.StringIO()
        x.write('<UL>\n')
        for user in pwd.getpwall():
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = user
            realname = string.split(pw_gecos,',')[0]
            if not realname:
                realname = pw_name
            fmtStr = '<LI><A HREF="%s/">%s (%s)</a>\n'
            if os.path.exists(os.path.join(pw_dir, self.userDirName)):
                x.write(fmtStr% (req.childLink(pw_name),realname,'file'))
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            if os.path.exists(twistdsock):
                linknm = '%s.twistd' % pw_name
                x.write(fmtStr% (req.childLink(linknm),realname,'twistd'))
        x.write('</UL>\n')
        return x.getvalue()

    def content(self, req):
        return "<CENTER>" + self.runBox(
            req,
            "Users with Homepages",
            self.listUsers, req) + "</CENTER>"

    def getChild(self, chnam, request):
        if chnam == '':
            return error.ErrorPage(http.NOT_FOUND,
                             "Bad URL",
                             "The empty string is not a valid user.")
        import pwd
        td = '.twistd'

        if chnam[-len(td):] == td:
            username = chnam[:-len(td)]
            sub = 1
        else:
            username = chnam
            sub = 0

        try:
            pw_name, pw_passwd, pw_uid, pw_gid, pw_gecos, pw_dir, pw_shell \
                     = pwd.getpwnam(username)
        except KeyError:
            return ErrorPage(http.NOT_FOUND,
                             "No Such User",
                             "The user %s was not found on this system." %
                             repr(username))
        if sub:
            twistdsock = os.path.join(pw_dir, self.userSocketName)
            rs = ResourceSubscription('unix',twistdsock,
                                      self.server.selector)
            self.putChild(chnam,rs)
            return rs
        else:
            return static.File(os.path.join(pw_dir, self.userDirName))
