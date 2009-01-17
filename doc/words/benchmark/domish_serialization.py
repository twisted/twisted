#!/usr/bin/python

# Benchmark which exercises the domish Element serialization code.
# This benchmark reports the number of Elements per second which can be serialized.

import sys
import time

from twisted.words.xish import domish


def slowfunc(elements, count):
    for i in xrange(count):
        for e in elements:
            e.toXml()

testDocument = """\
<stream>
    <iq xmlns='jabber:client' type='result' from='profile.chesspark.com' id='H_83833' to='arbiter.chesspark.com'/>
    <iq xmlns='jabber:client' from='arbiter.chesspark.com' id='H_84644' type='set' to='profile.chesspark.com'><pubsub xmlns='http://jabber.org/protocol/pubsub'><publish xmlns='http://jabber.org/protocol/pubsub' jid='jamboo@chesspark.com' node='http://jabber.org/protocol/profile'><profile xmlns='http://jabber.org/protocol/profile' jid='jamboo@chesspark.com'><x xmlns='jabber:x:data' type='result'><field var='playing'><value><game xmlns='http://onlinegamegroup.com/xml/chesspark-01' id='40280' black='jamboo@chesspark.com/cpwc' white='salmaaan28@chesspark.com/cpc'><playing/><time-control xmlns='http://onlinegamegroup.com/xml/chesspark-01' delayinc='-5' side='white'><control><time>1800</time></control></time-control><time-control xmlns='http://onlinegamegroup.com/xml/chesspark-01' delayinc='-5' side='black'><control><time>1800</time></control></time-control><variant xmlns='http://onlinegamegroup.com/xml/chesspark-01' name='standard'/><rating><category>Standard</category></rating></game></value></field></x></profile></publish></pubsub></iq>
    <iq xmlns='jabber:client' to='jamboo@chesspark.com/cpwc' type='result' id='7512:requestprofile' from='profile.chesspark.com'><profile xmlns='jabber:iq:profile' jid='salmaaan28@chesspark.com'><x xmlns='jabber:x:data' type='result'><field var='firstname'><value>salman</value></field><field var='surname'><value>kaliath</value></field><field var='email'><value>abdulrafeekk@yahoo.com</value></field><field var='wins'><value>1</value></field><field var='losses'><value>5</value></field><field var='nick'><value> </value></field><field var='roles'><value/></field><field var='titles'><value/></field><field var='ratings'><value><rating><rating>1064</rating><best>1500</best><worst>877</worst><wins>1</wins><losses>5</losses><rd>185</rd><category>Standard</category></rating></value></field><field xmlns='jabber:x:data' var='playing'><value><game xmlns='http://onlinegamegroup.com/xml/chesspark-01' white='salmaaan28@chesspark.com/cpc' black='jamboo@chesspark.com/cpwc' id='40280'><playing/><time-control side='white' delayinc='-5'><control><time>1800</time></control></time-control><time-control side='black' delayinc='-5'><control><time>1800</time></control></time-control><variant name='standard'/><rating><category>Standard</category></rating></game></value></field></x></profile></iq>
    <message to='jacktest@chesspark.com/cpwc' from='profile.chesspark.com'><event xmlns='http://jabber.org/protocol/pubsub#event'><items node='http://jabber.org/protocol/profile' jid='gumg@chesspark.com'><field xmlns='jabber:x:data' var='stopped-playing'><value><game xmlns='http://onlinegamegroup.com/xml/chesspark-01' white='gumg@chesspark.com/cpc' black='roboknight@chesspark.com/EngineBot' id='40267'><stopped-playing/><time-control side='white' delayinc='-5'><control><time>1800</time></control></time-control><time-control side='black' delayinc='-5'><control><time>1800</time></control></time-control><variant name='standard'/><rating><category>Standard</category></rating></game></value></field></items></event></message>
</stream>
"""


def main():
    elements = []
    parser = domish.elementStream()
    parser.DocumentStartEvent = lambda e: None
    parser.DocumentEndEvent = lambda: None
    parser.ElementEvent = elements.append
    parser.parse(testDocument)

    count = 1000
    before = time.time()
    slowfunc(elements, count)
    after = time.time()
    print 'Serialized %d elements in %0.2f seconds - %d elements/second' % (
        count * len(elements),
        after - before,
        (count * len(elements)) / (after - before))

if __name__ == '__main__':
    main()
