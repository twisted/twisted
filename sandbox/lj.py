import urllib
import string
import md5
import time
import os

from twisted.internet import tcp
from twisted.protocols import http
from twisted.python import defer

"""
URLs for Protocol Docs:
http://www.livejournal.com/developer/protocol.bml *DONE*
http://www.livejournal.com/developer/modelist.bml

Modes remaining:
* editfriendgroups
* editfriends
* friendof (this == just copy and paste)
* getdaycounts
* getfriendgroups (another copy and paste)
* syncitme
"""

class LiveJournalHTTPClient(http.HTTPClient):
    def __init__(self, lj, requestData, deferred, url):
        self.lj = lj
        self.body = urllib.urlencode(requestData)
        self.deferred = deferred
        self.url = url

    def connectionMade(self):
        self.sendCommand('POST', self.url)
        #self.sendHeader('Host',...) # XXX: figure this out
        self.sendHeader('Content-type', 'application/x-www-form-urlencoded')
        self.sendHeader('Content-length', len(self.body))
        if self.lj._ljUseFastServer:
            self.sendHeader('Cookie', 'ljfastserver=1')
        self.endHeaders()
        self.transport.write(self.body + '\r\n') # post
        
    def connectionLost(self):
        if self.deferred: self.deferred.errback('Connection Lost.')
        self.deferred = None

    def connectionFailed(self):
        if self.deferred: self.deferred.errback('Connection Failed!')
        self.deferred = None

    def handleStatus(self, version, status, message):
        if status != '200':
            self.deferred.errback('Bad Status from LiveJournal server: %s %s'
                                  % (status, message))

    def handleResponse(self, requestData):
        requestLines = string.split(requestData,'\n')
        requestDict = {}
        for line in range(0,len(requestLines)-1,2):
            key = requestLines[line]
            value = requestLines[line+1]
            requestDict[key] = value
        if not requestDict.has_key('success') or requestDict['success']=='FAIL':
            # error
            if requestDict.has_key('errmsg'): errmsg = requestDict['errmsg']
            else: errmsg = 'Server Error, try again later.'
            if self.deferred: self.deferred.errback(errmsg)
            self.deferred = None
        if self.deferred: self.deferred.callback(requestDict)
        self.deferred = None

def makeLJrequest(lj, requestDict, deferred, host = 'www.livejournal.com', port = 80,
                  url = '/interface/flat'):
    tcp.Client(host, port, LiveJournalHTTPClient(lj, requestDict, deferred, url))

class LiveJournalFriend:
    def __init__(self, userName, name, bgColor, fgColor, groupMask, userType):
        self.userName = userName
        self.name = name
        self.bgColor = bgColor
        self.fgColor = fgColor
        self.groupMask = groupMask
        self.userType = userType

    def __cmp__(self, otherThing):
        return cmp(self.__dict__, otherThing.__dict__)


class LiveJournalEvent:
    def __init__(self, subject, text, eventTime, security, allowMask, properties,
                 itemID, anum):
        self.subject = subject
        self.text = text
        ymd, hms = string.split(eventTime)
        year, month, day = map(int,string.split(ymd, '-'))
        hour, minute, second = map(int,string.split(hms, ':'))
        self.time = (year, month, day, hour, minute, second, 0, 0, 0)
            # ^ since time.strptime doesn't exist everywhere
        self.security = security
        self.itemID = itemID
        self.properties = properties
        self.allowMask = allowMask
        self.anum = anum

    def __cmp__(self, otherThing):
        return cmp(self.__dict__, otherThing.__dict__)
    

    def getProp(self, propName):
        return self.properties[propName]
    
    def getTalkID(self):
        """
        Returns the item id for use in talk*.bml links.
        """
        if anum == None:
            return self.itemID
        return (self.itemID * 256) + anum


class LiveJournalClient:
    _ljUseFastServer = 0
    _ljClientVersion = "Python-Twisted.LJ"
    def __init__(self, username, password, url = 'www.livejournal.com', port = 80):
        self.ljUsername = username
        self.ljHPassword = string.join(map(lambda x:"%02x"%x,map(ord,md5.new(password).digest())),"")
        self._ljURL = url
        self._ljPort = port
        self.ljMenus = []
        self.ljMoods = {} # moodid : moodname
        self.ljReverseMoods = {} # moodname : moodid
        self.ljFriendGroups = []
        self.ljFriends = []
        self.ljFriendsOf = []
        self.ljSharedJournals = []
        self.ljPictureKeywords = []
        self.ljPictureKeywordURLs = []
        self._ljCheckFriendsLastUpdate = None
        self._ljCheckFriendsLastValue = None
        self._ljCheckFriendsAfterTime = None
        self._ljLineEndings = {'nt' : 'pc', 'posix' : 'unix', 'mac' : 'mac',
                               'dos' : 'pc', 'os2' : 'pc', 'ce' : 'pc',
                               'riscos' : 'unix'}[os.name]


    def makeRequest(self, requestDict, deferred = None):
        if not deferred: deferred = defer.Deferred()
        makeLJrequest(self, requestDict, deferred, self._ljURL, self._ljPort)
        return deferred

    def _deferRequest(self, callback, requestDict, deferred):
        """
        utility method for protocol methods
        """
        if not deferred:
            deferred = defer.Deferred()
        d = self.makeRequest(requestDict)
        d.addCallbacks(callback, deferred.errback, callbackArgs = (deferred,))
        d.arm()
        return deferred

    def requestDict(self, mode):
        return {
            'mode' : mode,
            'user' :  self.ljUsername,
            'hpassword' : self.ljHPassword,
            'clientversion' : self._ljClientVersion
            }

    def login(self, getMenus = 0, getPicKws = 0, getPicKwURLs = 0, getMoods = 1, deferred = None):
        """
        Login to the LiveJournal server.
        
        Takes a optional deferred that will be called with a tuple consisting of
        this LiveJournalClient instance and the message returned by the server,
        if any.

        getmenus := ask for the URL menus (default: no)
        getpickkws := ask for the picture keywords (default: no)
        getpickkwurls := ask for the picture keyword urls (default: no)
        getmoods := get the mood IDs (default: yes)
        """
        requestDict = self.requestDict('login')

        if getMenus:
            requestDict['getmenus'] = 1
        if getPicKws:
            requestDict['getpickws'] = 1
        if getPicKwURLs:
            requestDict['getpickwurls'] = 1
        if getMoods:
            keys = self.ljMoods.keys()
            keys.sort()
            lastMoodID = (len(keys) and keys[-1]) or 0
            requestDict['getmoods'] = lastMoodID
        return self._deferRequest(self._cbLogin, requestDict, deferred)

    def _cbLogin(self, resultsDict, deferred):
        self.ljName = resultsDict['name']

        if resultsDict.has_key('message'):
            message = resultsDict['message']
        else:
            message = None

        maxFriendGroup = int(resultsDict['frgrp_maxnum'])+1
        self.ljFriendGroups = []
        for i in range(1,maxFriendGroup):
            if resultsDict.has_key('frgrp_%s_name' % i):
                groupName = resultsDict['frgrp_%s_name' % i]
                groupSort = resultsDict['frgrp_%s_sortorder' % i]
                self.ljFriendGroups.append([groupName,groupSort])

        numSharedJournals = int(resultsDict['access_count']) + 1
        for i in range(1,numSharedJournals):
            self.ljSharedJournals.append(resultsDict['access_%s' % i])

        if resultsDict.has_key('mood_count'):
            numNewMoods = int(resultsDict['mood_count']) + 1
            for i in range(1, numNewMoods):
                moodID = int(resultsDict['mood_%s_id' % i])
                moodName = resultsDict['mood_%s_name' % i]
                self.ljMoods[moodID] = moodName
                self.ljReverseMoods[moodName] = moodID

        if resultsDict.has_key('menu_0_count'):
            self.ljMenus = self._constructMenu(resultsDict)

        if resultsDict.has_key('pickw_count'):
            maxPicKW = int(resultsDict['pickw_count']) + 1
            for i in range(1, maxPicKW):
                self.ljPictureKeywords.append(resultsDict['pickw_%s' % i])

        if resultsDict.has_key('pickwurl_count'):
            maxPicKWURL = int(resultsDict['pickwurl_count']) + 1
            for i in range(1, maxPicKWURL):
                self.ljPictureKeywordURLs.append(resultsDict['pickwurl_%s' % i])

        if resultsDict.has_key('fastserver'):
            self.ljUseFastServer = 1 # SUPER SPEED

        deferred.armAndCallback((self,message))

    def _constructMenu(self, resultsDict, menu = 0):
        menuList = []
        menuCount = int(resultsDict['menu_%s_count' % menu]) + 1
        for i in range(1, menuCount):
            menuName = resultsDict['menu_%s_%s_text' % (menu, i)]
            if resultsDict.has_key('menu_%s_%s_url' % (menu, i)): # url
                menuType = 'url'
                menuData = resultsDict['menu_%s_%s_url' % (menu, i)]
            elif resultsDict.has_key('menu_%s_%s_sub' % (menu, i)): # submenu
                menuType = 'sub'
                menuSub = int (resultsDict['menu_%s_%s_sub' % (menu,i)])
                menuData = self._constructMenu(resultsDict, menuSub)
            else:
                menuType = 'sep'
                menuData = ''
            menuList.append((menuName, menuType, menuData))
        return menuList

    def getFriends(self, friendLimit = None, includeFriendOf = 0, includeGroups = 0, deferred = None):
        requestDict = self.requestDict('getfriends')
        if friendLimit:
            requestDict['friendlimit'] = friendLimit
        if includeFriendOf:
            requestDict['includefriendof'] = 1
        if includeGroups:
            requestDict['includegroups'] = 1
        return self._deferRequest(self._cbGetFriends, requestDict, deferred)

    def _cbGetFriends(self, resultsDict, deferred):
        friendCount = int(resultsDict['friend_count']) + 1
        friends = []
        for i in range(1, friendCount):
            userName = resultsDict['friend_%s_user' % i]
            name = resultsDict['friend_%s_name' % i]
            bgColor = resultsDict['friend_%s_bg' % i]
            fgColor = resultsDict['friend_%s_fg' % i]
            if resultsDict.has_key('friend_%s_groupmask' % i):
                groupMask = resultsDict['friend_%s_groupmask' % i]
            else:
                groupMask = None
            if resultsDict.has_key('friend_%s_type' % i):
                userType = resultsDict['friend_%s_type' % i]
            else:
                userType = None
            friends.append(LiveJournalFriend(userName, name, bgColor, fgColor, groupMask, userType))
        self.ljFriends = friends
        returnValue = [self, friends]
        if resultsDict.has_key('frgrp_maxnum'): # we asked for friend groups
            maxFriendGroup = int(resultsDict['frgrp_maxnum'])+1
            self.ljFriendGroups = []
            for i in range(1,maxFriendGroup):
                if resultsDict.has_key('frgrp_%s_name' % i):
                    groupName = resultsDict['frgrp_%s_name' % i]
                    groupSort = resultsDict['frgrp_%s_sortorder' % i]
                    self.ljFriendGroups.append([groupName,groupSort])
            returnValue.append(self.ljFriendGroups)
        if resultsDict.has_key('friendof_count'): # we asked for friends of us
            friendOfCount = int(resultsDict['friendof_count']) + 1
            friendsOf = []
            for i in range(1, friendOfCount):
                userName = resultsDict['friendof_%s_user' % i]
                name = resultsDict['friendof_%s_name' % i]
                bgColor = resultsDict['friendof_%s_bg' % i]
                fgColor = resultsDict['friendof_%s_fg' % i]
                if resultsDict.has_key('friendof_%s_type' % i):
                    userType = resultsDict['friendof_%s_type' % i]
                else:
                    userType = None
                friendsOf.append(LiveJournalFriend(userName, name, bgColor, fgColor, None, userType))
            self.ljFriendsOf = friendsOf
            returnValue.append(friendsOf)                

        deferred.armAndCallback(tuple(returnValue))

    def checkFriends(self, mask = None, deferred = None):
        if self._ljCheckFriendsLastValue:
            deferred.armAndCallback((self, 1)) # don't even bother polling
            return
        if self._ljCheckFriendsAfterTime and time.time() < self._ljCheckFriendsAfterTime:
            deferred.armAndCallback((self, 0)) # don't check yet
            return
        requestDict = self.requestDict('checkfriends')
        if mask:
            requestDict['mask'] = mask
        if self._ljCheckFriendsLastUpdate: requestDict['lastupdate'] = self._ljCheckLastUpdate
        return self._deferRequest(self._cbCheckFriends, requestDict, deferred)

    def _cbCheckFriends(self, resultsDict, deferred):
        self._ljCheckFriendsLastUpdate = resultsDict['lastupdate']
        self._ljCheckFriendsAfterTime = time.time() + int(resultsDict['interval'])
        self._ljCheckFriendsLastValue = int(resultsDict['new'])

        deferred.armAndCallback((self, self._ljCheckFriendsLastValue))

    def getEvents(self, selectType, itemID = None, howMany = None, beforeDate = None,
                  year = None, month = None, day = None, lastSync = None,
                  truncate = None, preferSubject = None, noProps = None,
                  useJournal = None, lineEndings = None, deferred = None):
        requestDict = self.requestDict('getevents')
        requestDict['selecttype'] = selectType
        if selectType == 'one':
            requestDict['itemid'] = itemID
        elif selectType == 'lastn':
            requestDict['howmany'] = howMany
            if beforeDate:
                requestDict['beforedate'] = beforeDate
        elif selectType == 'day':
            requestDict['year'] = year
            requestDict['month'] = month
            requestDict['day'] = day
        elif selectType == 'syncitems':
            requestDict['lastsync'] = lastSync
        if useJournal:
            requestDict['usejournal'] = useJournal
        if truncate:
            requestDict['truncate'] = truncate
        if preferSubject:
            requestDict['prefersubject'] = 1
        if noProps:
            requestDict['noprops'] = 1
        if useJournal:
            requestDict['usejournal'] = useJournal
        if not lineEndings:
            lineEndings = self._ljLineEndings
        requestDict['lineendings'] = lineEndings
        return self._deferRequest(self._cbGetEvents, requestDict, deferred)

    def _cbGetEvents(self, resultsDict, deferred):
        properties = {}
        if resultsDict.has_key('prop_count'):
            numProperties = int(resultsDict['prop_count']) + 1
            for i in range(1, numProperties):
                itemID = int(resultsDict['prop_%s_itemid' % i])
                name = resultsDict['prop_%s_name' % i]
                value = resultsDict['prop_%s_value' % i]
                if not properties.has_key(itemID):
                    properties[itemID] = []
                properties[itemID].append((name, value))
        numEvents = int(resultsDict['events_count']) + 1
        events = []
        for i in range(1, numEvents):
            itemID = int(resultsDict['events_%s_itemid' % i])
            eventTime = resultsDict['events_%s_eventtime' % i]
            text = urllib.unquote_plus(resultsDict['events_%s_event' % i])
            if resultsDict.has_key('events_%s_security' % i):
                security = resultsDict['events_%s_security' % i]
            else:
                security = None
            if security == 'allowmask':
                allowMask = int(resultsDict['events_%s_allowmask' % i])
            else:
                allowMask = None
            if resultsDict.has_key('events_%s_subject' % i):
                subject = resultsDict['events_%s_subject' % i]
            else:
                subject = None
            if resultsDict.has_key('events_%s_anum' % i):
                anum = int(resultsDict['events_%s_anum' % i])
            props = {}
            for k, v in properties.get(itemID, []):
                if k[:4] == 'opt_': v = int(v)
                props[k] = v
            events.append(LiveJournalEvent(subject, text, eventTime, security,
                                           allowMask, props, itemID, anum))
        deferred.armAndCallback((self, events))

    def postEvent(self, event, subject = None, properties = {}, security = None,
                  allowMask = None, eventTime = None, useJournal = None,
                  lineEndings = None, deferred = None):
        requestDict = self.requestDict('postevent')
        requestDict['event'] = event
        if subject:
            requestDict['subject'] = subject
        for k, v in properties.items():
            requestDict['prop_%s' % k] = v
        if security:
            requestDict['security'] = security
        if security == 'allowmask':
            requestDict['allowmask'] = allowMask
        if not eventTime:
            eventTime = time.localtime()
        requestDict['year'] = eventTime[0]
        requestDict['mon'] = eventTime[1]
        requestDict['day'] = eventTime[2]
        requestDict['hour'] = eventTime[3]
        requestDict['min'] = eventTime[4]
        if useJournal:
            requestDict['usejournal'] = useJournal
        if not lineEndings:
            lineEndings = self._ljLineEndings
        requestDict['lineendings'] = lineEndings
        return self._deferRequest(self._cbPostEvent, requestDict, deferred)

    def _cbPostEvent(self, resultsDict, deferred):
        itemID = int(resultsDict['itemid'])
        deferred.armAndCallback((self, itemID))

    def editEvent(self, itemID, event, subject = None, properties = {},
                  security = None, allowMask = None, eventTime = None,
                  useJournal = None, lineEndings = None, deferred = None):
        requestDict = self.requestDict('editevent')
        requestDict['itemid'] = itemID
        requestDict['event'] = event
        if subject:
            requestDict['subject'] = subject
        for k, v in properties.items():
            requestDict['prop_%s' % k] = v
        if security:
            requestDict['security'] = security
        if security == 'allowmask':
            requestDict['allowmask'] = allowMask
        if not eventTime:
            eventTime = time.localtime()
        requestDict['year'] = eventTime[0]
        requestDict['mon'] = eventTime[1]
        requestDict['day'] = eventTime[2]
        requestDict['hour'] = eventTime[3]
        requestDict['min'] = eventTime[4]
        if useJournal:
            requestDict['usejournal'] = useJournal
        if not lineEndings:
            lineEndings = self._ljLineEndings
        requestDict['lineendings'] = lineEndings
        return self._deferRequest(self._cbEditEvent, requestDict, deferred)

    def _cbEditEvent(self, resultsDict, deferred):
        deferred.armAndCallback(self)

if __name__ == '__main__':
    from twisted.internet import main
    def gotError(error):
        assert 0, "shouldn't get error: %s" % error

    def loggedIn((lj,message)):
        print "loggedIn",
        assert lj.ljName == 'Test Account', 'bad lj name %s' % lj.ljName
        assert message == "You need to validate your new email address.  Your old one was good, but since you've changed it, you need to re-validate the new one.  Visit the support area for more information.", 'bad message: %s' % message
        lj.oldFriendGroups = lj.ljFriendGroups
        lj.getFriends(includeFriendOf = 1, includeGroups = 1).addCallbacks(gotFriends, gotError)
        print '... done.'

    def gotFriends((lj, friends, groups, friendOf)):
        print "gotFriends",
        assert len(friends) == 1, 'should only be one friend, not %s' % len(friends)
        checkFriend = LiveJournalFriend('lj_biz', 'LiveJournal Business Discussion', '#ffffff', '#000000', None, 'community')
        assert friends == [checkFriend], 'bad return from getFriends: \n%s vs.\n%s' % (friends[0].__dict__, checkFriend.__dict__)
        assert groups == lj.oldFriendGroups, "friend groups don't match:\n%s\n%s" % (groups, lj.oldFriendGroups)
        del lj.oldFriendGroups
        lj.checkFriends().addCallbacks(checkedFriends, gotError)
        print '... done.'

    def checkedFriends((lj, new)):
        print "checkedFriends",
        assert new == 0, "shouldn't be any new posts"
        #print lj._ljCheckFriendsLastUpdate
        #print lj._ljCheckFriendsAfterTime - time.time()
        lj.getEvents('one', itemID = 1572).addCallbacks(gotEvent, gotError)
        print '... done.'

    def gotEvent((lj, events)):
        print "gotEvent",
        checkEvent = LiveJournalEvent(None, 'Babu', '2002-03-05 23:50:00', None,
                                      None, {'opt_nocomments' : 1,
                                             'picture_keyword' : 'Babu'},
                                      1572, 241)
        assert events == [checkEvent], 'events should be the same.\n%s\n%s' % (events[0].__dict__, checkEvent.__dict__)
        lj.getEvents('one', itemID = -1).addCallbacks(gotLastEvent, gotError)
        print '... done.'

    def gotLastEvent((lj, events)):
        print 'gotLastEvent',
        assert len(events) == 1, 'should only be one event, not %s' % len(events)
        lj.lastEvent = events[0]
        year, month, day, hour, minute, second, f, g, h = time.localtime()
        lj.postEvent('This == a test of the Twisted LiveJournal system.',
                     subject = 'Twisted LiveJournal Test',
                     properties = {'current_mood' : 5},
                     security = 'private').addCallbacks(
                         postedEvent, gotError)
        print '... done.'

    def postedEvent((lj, itemID)):
        print 'postedEvent',
        lj.lastItemID = itemID
        lj.getEvents('lastn', howMany = 2).addCallbacks(got2Events, gotError)
        print '... done.'

    def got2Events((lj, events)):
        print 'got2Events',
        assert len(events)==2, 'should have gotten 2 events, not %s' % len(events)
        assert events[1] == lj.lastEvent, 'last events should be ==\n%s\n%s' % (events[1].__dict__, lj.lastEvent.__dict__)
        assert events[0].subject == 'Twisted LiveJournal Test'
        assert events[0].text == 'This == a test of the Twisted LiveJournal system.'
        assert events[0].properties == {'current_mood' : '5'}
        assert events[0].security == 'private'
        #assert events[0].allowMask == 8
        assert events[0].itemID == lj.lastItemID
        lj.editEvent(lj.lastItemID, '').addCallbacks(deletedEvent, gotError)
        del lj.lastItemID
        print '... done.'

    def deletedEvent(lj):
        print 'deletedEvent',
        lj.getEvents('one', itemID = -1).addCallbacks(checkEvent, gotError)
        print '... done.'

    def checkEvent((lj, events)):
        print 'checkEvent',
        assert events == [lj.lastEvent], 'last events should be ==\n%s\n%s' % (events[0].__dict__, lj.lastEvent.__dict__)
        print '... done.'
        print 'ALL TESTS PASS.'
        main.shutDown()

    lj = LiveJournalClient('test', 'test')
    print "making login request"
    lj.login().addCallbacks(loggedIn, gotError) # XXX: == this good/bad/normal?
    #lj.getEvents('one', itemID = -1).addCallbacks(gotLastEvent, gotError)
    print "didn't block, good"
    main.run()