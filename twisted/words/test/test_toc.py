# Copyright (c) 2001-2005 Twisted Matrix Laboratories.
# See LICENSE for details.


from twisted.trial import unittest

from twisted.words.protocols import toc
from twisted.internet import protocol, main
from twisted.python import failure

import StringIO
from struct import pack,unpack

class StringIOWithoutClosing(StringIO.StringIO):
    def close(self):
        pass
        
class DummyTOC(toc.TOC):
    """
    used to override authentication, now overrides printing.
    """
    def _debug(self,data):
        pass
SEQID=1001
def flap(type,data):
    global SEQID
    send="*"
    send=send+pack("!BHH",type,SEQID,len(data))
    send=send+data
    SEQID=SEQID+1
    return send
def readFlap(data):
    if data=="": return [None,""]
    null,type,seqid,length=unpack("!BBHH",data[:6])
    val=data[6:6+length]
    return [[type,val],data[6+length:]]
    
class TOCGeneralTestCase(unittest.TestCase):
    """
    general testing of TOC functions.
    """
    def testTOC(self):
        self.runTest()
    def runTest(self):
        USERS=2
        data=range(USERS)
        data[0]=("FLAPON\r\n\r\n",\
        flap(1,"\000\000\000\001\000\001\000\004test"),\
        flap(2,"toc_signon localhost 9999 test 0x100000 english \"penguin 0.1\"\000"),\
        flap(2,"toc_add_buddy test\000"),\
        flap(2,"toc_init_done\000"),\
        flap(2,"toc_send_im test \"hi\"\000"),\
        flap(2,"toc_send_im test2 \"hello\"\000"),\
        flap(2,"toc_set_away \"not here\"\000"),\
        flap(2,"toc_set_idle 602\000"),\
        flap(2,"toc_set_idle 0\000"),\
        flap(2,"toc_set_away\000"),\
        flap(2,"toc_evil test norm\000"),\
        flap(2,"toc_chat_join 4 \"Test Chat\"\000"),\
        flap(2,"toc_chat_send 0 \"hello\"\000"),\
        #flap(2,"toc_chat_leave 0\000")) #,\
        flap(2,"toc_chat_invite 0 \"come\" ooga\000"),\
        #flap(2,"toc_chat_accept 0\000"),\
        flap(5,"\000"),\
        flap(2,"toc_chat_whisper 0 ooga \"boo ga\"\000"),\
        flap(2,"toc_chat_leave 0"),\
        flap(5,"\000"))
        data[1]=("FLAPON\r\n\r\n",\
        flap(1,"\000\000\000\001\000\001\000\004ooga"),\
        flap(2,"toc_signon localhost 9999 ooga 0x100000 english \"penguin 0.1\"\000"),\
        flap(2,"toc_add_buddy test\000"),\
        flap(2,"toc_init_done\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        #flap(5,"\000"),\
        #flap(5,"\000"),\
        #flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        flap(5,"\000"),\
        #flap(5,"\000"),\
        flap(2,"toc_chat_accept 0\000"),\
        flap(2,"toc_chat_send 0 \"hi test\"\000"),\
        flap(5,"\000"),\
        flap(2,"toc_chat_leave 0\000"))
        strings=range(USERS)
        for i in strings:
            strings[i]=StringIOWithoutClosing()
        fac=toc.TOCFactory()
        dummy=range(USERS)
        for i in dummy:
            dummy[i]=DummyTOC()
            dummy[i].factory=fac
            dummy[i].makeConnection(protocol.FileWrapper(strings[i]))
        while reduce(lambda x,y:x+y,map(lambda x:x==(),data))!=USERS:
            for i in range(USERS):
                d=data[i]
                if len(d)>0:
                    k,data[i]=d[0],d[1:]
                    for j in k:
                        dummy[i].dataReceived(j) # test by doing a character at a time
                else:
                    dummy[i].connectionLost(failure.Failure(main.CONNECTION_DONE))
        values=range(USERS)
        for i in values:
            values[i]=strings[i].getvalue()
        flaps=map(lambda x:[],range(USERS))
        for value in values:
            i=values.index(value)
            f,value=readFlap(value)
            while f:
                flaps[i].append(f)
                f,value=readFlap(value)
        ts=range(USERS)
        for t in ts:
            ts[t]=dummy[t].signontime
        shouldequal=range(USERS)
        shouldequal[0]=[ \
        [1,"\000\000\000\001"],\
        [2,"SIGN_ON:TOC1.0\000"],\
        [2,"NICK:test\000"],\
        [2,"CONFIG:\00"],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: O\000"%ts[0]],\
        [2,"IM_IN:test:F:hi\000"],\
        [2,"ERROR:901:test2\000"],\
        #[2,"UPDATE_BUDDY:test:T:0:%s:0: O\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:10: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: O\000"%ts[0]],\
        [2,"EVILED:10:test\000"],\
        [2,"UPDATE_BUDDY:test:T:10:%s:0: O\000"%ts[0]],\
        [2,"CHAT_JOIN:0:Test Chat\000"],\
        [2,"CHAT_UPDATE_BUDDY:0:T:test\000"],\
        [2,"CHAT_IN:0:test:F:hello\000"],\
        [2,"CHAT_UPDATE_BUDDY:0:T:ooga\000"],\
        [2,"CHAT_IN:0:ooga:F:hi test\000"],\
        [2,"CHAT_LEFT:0\000"]]
        shouldequal[1]=[ \
        [1,"\000\000\000\001"],\
        [2,"SIGN_ON:TOC1.0\000"],\
        [2,"NICK:ooga\000"],\
        [2,"CONFIG:\000"],\
        #[2,"UPDATE_BUDDY:test:T:0:%s:0: O\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:10: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: OU\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:0:%s:0: O\000"%ts[0]],\
        [2,"UPDATE_BUDDY:test:T:10:%s:0: O\000"%ts[0]],\
        [2,"CHAT_INVITE:Test Chat:0:test:come\000"],\
        [2,"CHAT_JOIN:0:Test Chat\000"],\
        [2,"CHAT_UPDATE_BUDDY:0:T:test:ooga\000"],\
        [2,"CHAT_IN:0:ooga:F:hi test\000"],\
        [2,"CHAT_IN:0:test:T:boo ga\000"],\
        [2,"CHAT_UPDATE_BUDDY:0:F:test\000"],\
        [2,"CHAT_LEFT:0\000"]]
        if flaps!=shouldequal:
            for i in range(len(shouldequal)):
                for j in range(len(shouldequal[i])):
                    if shouldequal[i][j]!=flaps[i][j]:
                        raise AssertionError("GeneralTest Failed!\nUser %s Line %s\nactual:%s\nshould be:%s"%(i,j,flaps[i][j],shouldequal[i][j]))
            raise AssertionError("GeneralTest Failed with incorrect lengths!")
class TOCMultiPacketTestCase(unittest.TestCase):
    """
    i saw this problem when using GAIM.  It only read the flaps onces per dataReceived, and would basically block if it ever received two packets together in one dataReceived.  this tests for that occurance.
    """
    def testTOC(self):
        self.runTest()
    def runTest(self):
        packets=["FLAPON\r\n\r\n",\
         flap(1,"\000\000\000\001\000\001\000\004test"),\
         flap(2,"toc_signon null 9999 test 0x100000 english \"penguin 0.1\"\000"),\
         flap(2,"toc_init_done\000"),\
         flap(2,"toc_send_im test hi\000")]
        shouldbe=[[1,"\000\000\000\001"],\
         [2,"SIGN_ON:TOC1.0\000"],\
         [2,"NICK:test\000"],\
         [2,"CONFIG:\000"],\
         [2,"IM_IN:test:F:hi\000"]]
        data=""
        for i in packets:
            data=data+i
        s=StringIOWithoutClosing()
        d=DummyTOC()
        fac=toc.TOCFactory()
        d.factory=fac
        d.makeConnection(protocol.FileWrapper(s))
        d.dataReceived(data)
        d.connectionLost(failure.Failure(main.CONNECTION_DONE))
        value=s.getvalue()
        flaps=[]
        f,value=readFlap(value)
        while f:
            flaps.append(f)
            f,value=readFlap(value)
        if flaps!=shouldbe:
            for i in range(len(flaps)):
                if flaps[i]!=shouldbe[i]:raise AssertionError("MultiPacketTest Failed!\nactual:%s\nshould be:%s"%(flaps[i],shouldbe[i]))
            raise AssertionError("MultiPacketTest Failed with incorrect length!, printing both lists\nactual:%s\nshould be:%s"%(flaps,shouldbe))
class TOCSavedValuesTestCase(unittest.TestCase):
    def testTOC(self):
        self.runTest()
    def runTest(self):
        password1=toc.roast("test pass")
        password2=toc.roast("pass test")
        beforesend=[\
         "FLAPON\r\n\r\n",\
         flap(1,"\000\000\000\001\000\001\000\004test"),\
         flap(2,"toc_signon localhost 9999 test %s english \"penguin 0.1\"\000"%password1),\
         flap(2,"toc_init_done\000"),\
         flap(2,"toc_set_config \"{m 4}\"\000"),\
         flap(2,"toc_format_nickname BOOGA\000"),\
         flap(2,"toc_format_nickname \"T E S T\"\000"),\
         flap(2,"toc_change_passwd \"testpass\" \"pass test\"\000"),\
         flap(2,"toc_change_passwd \"test pass\" \"pass test\"\000")]
        beforeexpect=[\
         [1,"\000\000\000\001"],\
         [2,"SIGN_ON:TOC1.0\000"],\
         [2,"NICK:test\000"],\
         [2,"CONFIG:\000"],\
         [2,"ERROR:911\000"],\
         [2,"ADMIN_NICK_STATUS:0\000"],\
         [2,"ERROR:911\000"],\
         [2,"ADMIN_PASSWD_STATUS:0\000"]]
        badpasssend=[\
         "FLAPON\r\n\r\n",\
         flap(1,"\000\000\000\001\000\001\000\004test"),\
         flap(2,"toc_signon localhost 9999 test 0x1000 english \"penguin 0.1\"\000"),\
         flap(2,"toc_init_done")]
        badpassexpect=[\
         [1,"\000\00\000\001"],\
         [2,"ERROR:980\000"]]
        goodpasssend=[\
         "FLAPON\r\n\r\n",\
         flap(1,"\000\000\000\001\000\001\000\004test"),\
         flap(2,"toc_signon localhost 9999 test %s english \"penguin 0.1\"\000"%password2),\
         flap(2,"toc_init_done")]
        goodpassexpect=[\
         [1,"\000\000\000\001"],\
         [2,"SIGN_ON:TOC1.0\000"],\
         [2,"NICK:T E S T\000"],\
         [2,"CONFIG:{m 4}\000"]]
        fac=toc.TOCFactory()
        d=DummyTOC()
        d.factory=fac
        s=StringIOWithoutClosing()
        d.makeConnection(protocol.FileWrapper(s))
        for i in beforesend:
            d.dataReceived(i)
        d.connectionLost(failure.Failure(main.CONNECTION_DONE))
        v=s.getvalue()
        flaps=[]
        f,v=readFlap(v)
        while f:
            flaps.append(f)
            f,v=readFlap(v)
        if flaps!=beforeexpect:
            for i in range(len(flaps)):
                if flaps[i]!=beforeexpect[i]:
                    raise AssertionError("SavedValuesTest Before Failed!\nactual:%s\nshould be:%s"%(flaps[i],beforeexpect[i]))
            raise AssertionError("SavedValuesTest Before Failed with incorrect length!\nactual:%s\nshould be:%s"%(flaps,beforeexpect))
        d=DummyTOC()
        d.factory=fac
        s=StringIOWithoutClosing()
        d.makeConnection(protocol.FileWrapper(s))
        for i in badpasssend:
            d.dataReceived(i)
        d.connectionLost(failure.Failure(main.CONNECTION_DONE))
        v=s.getvalue()
        flaps=[]
        f,v=readFlap(v)
        while f:
            flaps.append(f)
            f,v=readFlap(v)
        if flaps!=badpassexpect:
            for i in range(len(flaps)):
                if flaps[i]!=badpassexpect[i]:
                    raise AssertionError("SavedValuesTest BadPass Failed!\nactual:%s\nshould be:%s"%(flaps[i],badpassexpect[i]))
            raise AssertionError("SavedValuesTest BadPass Failed with incorrect length!\nactual:%s\nshould be:%s"%(flaps,badpassexpect))
        d=DummyTOC()
        d.factory=fac
        s=StringIOWithoutClosing()
        d.makeConnection(protocol.FileWrapper(s))
        for i in goodpasssend:
            d.dataReceived(i)
        d.connectionLost(failure.Failure(main.CONNECTION_DONE))
        v=s.getvalue()
        flaps=[]
        f,v=readFlap(v)
        while f:
            flaps.append(f)
            f,v=readFlap(v)
        if flaps!=goodpassexpect:
            for i in range(len(flaps)):
                if flaps[i]!=goodpassexpect[i]:
                    raise AssertionError("SavedValuesTest GoodPass Failed!\nactual:%s\nshould be:%s"%(flaps[i],goodpassexpect[i]))
            raise AssertionError("SavedValuesTest GoodPass Failed with incorrect length!\nactual:%s\nshould be:%s"%(flaps,beforeexpect))
class TOCPrivacyTestCase(unittest.TestCase):
    def runTest(self):
        sends=["FLAPON\r\n\r\n",\
         flap(1,"\000\000\000\001\000\001\000\004test"),\
         flap(2,"toc_signon localhost 9999 test 0x00 english penguin\000"),\
         flap(2,"toc_init_done\000"),\
         flap(2,"toc_add_deny\000"),\
         flap(2,"toc_send_im test 1\000"),\
         flap(2,"toc_add_deny test\000"),\
         flap(2,"toc_send_im test 2\000"),\
         flap(2,"toc_add_permit\000"),\
         flap(2,"toc_send_im test 3\000"),\
         flap(2,"toc_add_permit test\000"),\
         flap(2,"toc_send_im test 4\000")]
        expect=[[1,"\000\000\000\001"],\
         [2,"SIGN_ON:TOC1.0\000"],\
         [2,"NICK:test\000"],\
         [2,"CONFIG:\000"],\
         [2,"IM_IN:test:F:1\000"],\
         [2,"ERROR:901:test\000"],\
         [2,"ERROR:901:test\000"],\
         [2,"IM_IN:test:F:4\000"]]
        d=DummyTOC()
        d.factory=toc.TOCFactory()
        s=StringIOWithoutClosing()
        d.makeConnection(protocol.FileWrapper(s))
        for i in sends:
            d.dataReceived(i)
        d.connectionLost(failure.Failure(main.CONNECTION_DONE))
        v=s.getvalue()
        flaps=[]
        f,v=readFlap(v)
        while f:
            flaps.append(f)
            f,v=readFlap(v)
        if flaps!=expect:
            for i in range(len(flaps)):
                if flaps[i]!=expect[i]:
                    raise AssertionError("PrivacyTest Before Failed!\nactual:%s\nshould be:%s"%(flaps[i],expect[i]))
            raise AssertionError("PrivacyTest Before Failed with incorrect length!\nactual:%s\nshould be:%s"%(flaps,expect))         
testCases=[TOCGeneralTestCase,TOCMultiPacketTestCase,TOCSavedValuesTestCase,TOCPrivacyTestCase]

