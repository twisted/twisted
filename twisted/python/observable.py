
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

"""
A group of classes which implement the observer/observable and
publisher/subscriber pattern.
"""

# System Imports
import types
import sys
import string
import copy

# Sibling Imports
import reflect
import log

class _DontTell:
    def __cmp__(self,other):
        if isinstance(other,_DontTell):
            return 0
        else:
            return -1

    def __hash__(self): return id(self)
    def __repr__(self):
        return "observable.DontTell"

class _Gone:
    def __cmp__(self,other):
        if isinstance(other,_Gone):
            return 0
        else:
            return -1

    def __hash__(self): return id(self)
    def __repr__(self):
        return "observable.Gone"

DontTell=_DontTell()
Gone=_Gone()

class Dynamic:
    def __init__(self, caller=None):
        if caller:
            self.evaluate=caller

    def evaluate(self,observer,hash=None,key=None):
        log.msg('observe.py: Dynamic.evaluate called directly --> override this')
        log.msg('observer %s\nhash %s\nkey %s'%(observer,hash,key))
        return DontTell

    def __call__(self,observer,hash=None,key=None):
        if type(observer)==types.MethodType:
            observer=observer.im_self
        return self.evaluate(observer,hash,key)

def propertize(self, observer,key,prop):
    if isinstance(prop,Dynamic): p=prop(observer,self,key)
    else: p=prop
    if p == DontTell: raise p
    return p

class EventSource:
    def __init__(self):
        self.listeners={}

    def bind(self, event, command, args=()):
        if not self.listeners.has_key(event):
            self.listeners[event]=[]
        self.listeners[event].append(command)

    def fire(self, event, *args,**kw):
        for listener in self.listeners[event]:
            apply(listener,args,kw)

class Observable:
    def __init__(self):
        self.observers=[]

    def addObserver(self, observer):
        """Observable.addObserver(observer)
        Add a method which will be called when this observer's
        notify() is executed."""
        self.observers.append(observer)
        self.observers = self.observers

    def removeObserver(self, observer):
        """Observable.removeObserver(observer)
        Remove a previously-added method would have been called when
        this observer's notify() was executed"""

        self.observers.remove(observer)
        self.observers = self.observers

    def notify(self, *rgs):
        """Observable.notify(*rgs)
        call all observers of this observable with (self,)+rgs"""
        args=(self,)+rgs
        for observer in self.observers:
            self.tell(observer, args)
        self.observers = self.observers

    def tell(self,observer,args):
        apply(observer,args)

class Publisher:
    subscribers = None

    def unsubscribe(self, channel, subscriber):
        """Publisher.unsubscribe(channel, subscriber)

        Unsubscribe a previously subscribed subscriber method from a
        particular channel."""
        subs = self.subscribers[channel]
        subs.remove(subscriber)
        if not subs:
            del self.subscribers[channel]


    def subscribe(self, channel, subscriber):
        """Publisher.subscribe(channel, subscriber)

        Subscribe a 'subscriber' method to a 'channel' key (a python
        identifier): whenver 'publish' is called with an equivalent
        'channel' argument, , the subscriber will be called with the
        signature (sender, channel, data), where 'sender' is this
        publisher, 'channel' is the chosen channel key, and 'data' is
        some arbitrary data. 'publish' will also call the method
        on_%(channel)s on this object with data as the only
        argument (plus the implicit self!) """

        if self.subscribers is None:
            self.subscribers = {}

        l = self.subscribers.get(channel,[])
        l.append(subscriber)
        self.subscribers[channel] = l


    def publish(self, channel, data):
        """Publisher.publish(channel,data)

        Publish the given data to a channel -- call all subscriber
        methods to this channel, with the arguments (self, channel,
        data), and the default subscriber (named on_%s) with only
        'data' as an argument"""
        # Call the default subscriber
        defaultSubscriber = getattr(self, "on_%s" % channel, None)
        if defaultSubscriber is not None:
            try:
                defaultSubscriber(data)
            except:
                log.deferr()
        # Now call all the regular subscribers.
        if not self.subscribers: return
        for subscriber in self.subscribers.get(channel,()):
            try:
                subscriber(self, channel, data)
            except:
                log.deferr()

class WhenMethodSubscription:
    """
    This is a helper class to make the whole concept of when_
    method subscriptions more friendly to pickling.
    """

    def __init__(self, subscriber, attribute, channel):
        self.subscriber = subscriber
        self.attribute = attribute
        self.channel = channel

    def __cmp__(self, other):
        if other is self:
            return 0
        if not reflect.isinst(other, WhenMethodSubscription):
            return -1
        for attr in 'subscriber','attribute','channel':
            retval = cmp(getattr(self,attr),getattr(other,attr))
            if retval != 0:
                return retval
        return 0

    def __repr__(self):
        return "<WhenMethodSubscription %s %s %s>" % (repr(self.subscriber),
                                                      self.attribute,
                                                      repr(self.channel))

    def __call__(self, publisher, channel, message):
        assert channel == self.channel, "Channel should be the same."
        method = getattr(self.subscriber,
                         "when_"+self.attribute+"_"+self.channel, None)
        if method is None:
            log.msg("Unsubscribe due to Persistent Inconsistency:")
            log.msg(string.join(map(
                str,(self.publisher, self.subscriber,
                     self.attribute, self.channel))))
            self.publisher.unsubscribe(self, publisher, subscriber, attribute)
            return None
        else:
            return method(publisher, channel, message)


def registerWhenMethods(Class):
    sa = Class._subscriberAttributes = {}
    for base in Class.__bases__:
        if issubclass(base, Subscriber):
            sa.update(base._subscriberAttributes)
    # The structure of this dictionary is
    # {attributeName: {eventName: [listOfHandlers]}}
    # The handler 'None' is treated specially, and the instance-method
    # is subscribed when it is encountered.
    for name,method in Class.__dict__.items():
        # I want to turn method names like when_place_enter into a
        # dictionary like {'place': {'enter': None}}.
        if type(method) == types.FunctionType:
            specname = string.split(name,'_')
            # Okay.  We've got some special naming stuff here.
            if not len(specname) > 2:
                continue
            if not specname[0] == 'when':
                continue
            evtname = specname[1]
            attrname = string.join(specname[2:],'_')
            evtdict = sa.get(evtname,{})
            evtdict[attrname] = [None]
            sa[evtname] = evtdict

class Subscriber(reflect.Accessor):
    _subscriberAttributes = {}
    def subscribeToAttribute(self, attribute, channel, callback):
        assert callable(callback), "Callback must be a callable type."
        if self._subscriberAttributes is self.__class__._subscriberAttributes:
            self._subscriberAttributes = copy.deepcopy(self._subscriberAttributes)
        channels = self._subscriberAttributes.get(attribute,{})
        handlers = channels.get(channel,[])
        handlers.append(callback)
        channels[channel] = handlers
        self._subscriberAttributes[attribute] = channels
        currentPublisher = getattr(self, attribute, None)
        if reflect.isinst(currentPublisher, Publisher):
            currentPublisher.subscribe(channel, callback)

    def unsubscribeFromAttribute(self, attribute, channel, callback):
        assert not (self._subscriberAttributes is
                    self.__class__._subscriberAttributes),\
                    "No attribute channels have been subscribed."
        channels = self._subscriberAttributes[attribute]
        handlers = channels[channel]
        handlers.remove(callback)
        currentPublisher = getattr(self, attribute, None)
        if reflect.isinst(currentPublisher, Publisher):
            currentPublisher.unsubscribe(channel, callback)

    def reallyDel(self, key):
        self._doSub(key, None)
        reflect.Accessor.reallyDel(self,key)

    def reallySet(self, key, val):
        self._doSub(key,val)
        reflect.Accessor.reallySet(self,key,val)

    def _doSub(self, key, val):
        attributeInfo = self._subscriberAttributes.get(key,{}).items()
        previousAttribute = getattr(self,key,None)
        if reflect.isinst(previousAttribute, Publisher):
            for event, handlers in attributeInfo:
                for handler in handlers:
                    if handler is None:
                        handler = WhenMethodSubscription(self, key, event)
                        # handler = getattr(self, "when_"+key+"_"+event)
                    try:
                        previousAttribute.unsubscribe(event, handler)
                    except KeyError:
                        # Since this deals with when_ methods, the
                        # most likely time for an exception to be
                        # thrown here is when you've added a when
                        # method.  There's no point in stopping
                        # execution there.
                        pass

        if reflect.isinst(val, Publisher):
            for event, handlers in attributeInfo:
                for handler in handlers:
                    if handler is None:
                        handler = WhenMethodSubscription(self, key, event)
                        #handler = getattr(self, "when_"+key+"_"+event)
                    val.subscribe(event, handler)

class Hash(Observable):

    def __init__(self,properties=None):
        Observable.__init__(self)
        if properties is None:
            properties={}
        self.properties=properties

    def tell(self,observer,targs):
        self2,key,value=targs
        # I assume I haven't seen this yet.
        already_seen=0
        try:
            # Does this observer think there's something in this hash
            # under this key already?
            propertize(self,observer,key,self[key])
            # Correction, I have.
            already_seen=1
        except _DontTell:
            # If not, well,
            if targs[2]==Gone:
                # if we were just going to tell them that it was gone,
                # forget about it.
                return
        except KeyError:
            # That wasn't even in the dictionary before!
            pass
        try:
            apply(observer,
                  (self2, key,
                   propertize(self,observer,key,value)))
        except _DontTell:
            # Okay, so this observer isn't supposed to know about this
            # property.
            if already_seen:
                # If they already have it "in view", tell them it's
                # gone now.
                apply(observer,(self2,key,Gone))
            # Otherwise, well, they don't know that anything has happened.

    def addObserver(self, observer):
        Observable.addObserver(self,observer)
        for k,v in self.properties.items():
            self.tell(observer,(self,k,v))

    def __setitem__(self, key,val):
        self.notify(key,val)
        self.properties[key]=val

    def __getitem__(self, key):
        return self.properties[key]

    def __len__(self):
        return len(self.properties)

    def __delitem__(self, key):
        self.notify(key,Gone)
        del self.properties[key]

    def keys(self):
        return self.properties.keys()

    def values(self):
        return self.properties.values()

    def items(self):
        return self.properties.items()

    def update(self,dict):
        for k,v in dict.items():
            self[k]=v

    def has_key(self,key):
        return self.properties.has_key(key)

    def __repr__(self):
        if self.observers:
            x=repr(self.observers)
        else:
            x=""
        return "observable.Hash(%s%s)"%(repr(self.properties),x)


class Delegator:
    def __init__(self, callhash):
        self.hash=callhash
    def __call__(self, *args):
        try: observer=self.hash[args[1]]
        except: 'no delegation'
        else: apply(self.hash[args[1]],args)
