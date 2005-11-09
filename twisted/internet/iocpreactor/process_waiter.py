# Copyright (c) 2001-2004 Twisted Matrix Laboratories.
# See LICENSE for details.

"""Support for waiting for processes using 63 waits per thread
to avoid Windows limitations to *WaitForMultipleObjects*.

API Stability: unstable

Maintainer: U{Justin Johnson<mailto:justinjohnson@gmail.com>}
"""

# Win32 imports
import win32api
import win32gui
import win32con
import win32file
import win32pipe
import win32process
import win32security
from win32event import CreateEvent, SetEvent, WaitForSingleObject
from win32event import MsgWaitForMultipleObjects, WAIT_OBJECT_0
from win32event import WAIT_TIMEOUT, INFINITE, QS_ALLINPUT, QS_POSTMESSAGE
from win32event import QS_ALLEVENTS

# Zope & Twisted imports
from zope.interface import implements
from twisted.internet import error
from twisted.python import failure, components
from twisted.internet.interfaces import IProcessTransport

# sibling imports
import ops

# System imports
import os
import sys
import re
import time
import threading
import itertools

# Counter for uniquely identifying pipes
counter = itertools.count(1)

# Message ID must be greater than WM_USER or the system will do
# marshalling automatically.
WM_NEW_PHANDLE = win32con.WM_USER + 1
WM_CLOSE_THREAD = win32con.WM_USER + 2

class ProcessWaiter(object):
    """Waiter
    """
    usedThreads = []  # threads waiting on 63 process handles
    availableThreads = [] # threads waiting on less than 63 process handles

    threadToNumProcessHandles = {}
    threadToMsgWindowCreationEvent = {} # event signalled when msg window created
    threadToMsgWindowCreated = {} # boolean indicated msg window is created
    needWaiting = {} # used to pass process handles to new WFMO thread
    phandleToTransport = {} # so we can call methods on the transport when a proc handle is signalled
    threadToMsgWindow = {} # since we need the window to call PostMessage
    phandleKeyToThreadHandle = {} # proc handle keys passed to PostThreadMessage to tell thread to wait on new proc handle
    phandleToPhandleKey = {}
    threadToNumEnded = {}

    def __init__(self, reactor):
        def stopThreads():
            for t in self.threadToMsgWindow.keys():
                # PostMessage blocks for dead threads
                if t.isAlive() and self.threadToMsgWindowCreated[t]:
                    win32api.PostMessage(
                        self.threadToMsgWindow[t], # thread id
                        WM_CLOSE_THREAD, # message 
                        0, # wParam
                        0 # lParam
                        )
        reactor.addSystemEventTrigger("before", "shutdown", stopThreads)
    
    def beginWait(self, reactor, processHandle, processTransport):
        self.reactor = reactor
        # Win32 APIs can't be passed python objects, so we pass a key
        # that maps to the object in a dict that the thread has access to
        processHandleKey = counter.next()
        self.phandleToPhandleKey[processHandle] = processHandleKey
        self.phandleToTransport[processHandle] = processTransport
        self.needWaiting[processHandleKey] = processHandle
        self.realPid = os.getpid()
        self.notifyOnExit(processHandle, processTransport)

    def notifyOnExit(self, processHandle, processTransport):
        processHandleKey = self.phandleToPhandleKey[processHandle]
        
        # If there are available threads, use one of them
        if len(self.availableThreads) > 0:
            wfmoThread = self.availableThreads[0]
            self.threadToNumProcessHandles[wfmoThread] += 1
            self.phandleKeyToThreadHandle[processHandleKey] = wfmoThread
            # Update used/available thread lists
            if self.threadToNumProcessHandles[wfmoThread] == 63:
                self.usedThreads.append(wfmoThread)
                self.availableThreads.remove(wfmoThread)
            # Make sure the message window has been created so
            # we can send messages to the thread.
            if self.threadToMsgWindowCreated[wfmoThread] is False:
                val = WaitForSingleObject(self.threadToMsgWindowCreationEvent[wfmoThread], INFINITE)
                if val != WAIT_OBJECT_0:
                    raise RuntimeError("WaitForSingleObject returned %d.  It should only return %d" % (val, WAIT_OBJECT_0))
            # Notify the thread that it should wait on the process handle.
            if win32api.PostMessage(
                    self.threadToMsgWindow[wfmoThread],
                    WM_NEW_PHANDLE, # message 
                    processHandleKey, # wParam
                    0 # lParam
                    ) == 0:
                raise Exception("Failed to post thread message!")
        else:
            # Create a new thread and wait on the proc handle
            wfmoThread = threading.Thread(
                    target=self.doWaitForProcessExit,
                    args=(processHandleKey,),
                    name="iocpreactor.process_waiter.ProcessWaiter.waitForProcessExit pid=%d" % self.realPid)
            # Create a window creation event that will be triggered from the thread
            self.threadToMsgWindowCreationEvent[wfmoThread] = CreateEvent(None, 0, 0, None)
            self.threadToMsgWindowCreated[wfmoThread] = False
            self.threadToNumProcessHandles[wfmoThread] = 1
            self.availableThreads.append(wfmoThread)
            self.phandleKeyToThreadHandle[processHandleKey] = wfmoThread
            wfmoThread.start()
    
    def doWaitForProcessExit(self, processHandleKey):
        # Create a hidden window that will receive messages for things
        # like adding new handles to wait on or quitting the thread.
        # I use the Button class because I'm too lazy to register my own.
        theWindow = win32gui.CreateWindow("Button", # lpClassName
                                          "",       # lpWindowName
                                          0,        # dwStyle
                                          0,        # x
                                          0,        # y
                                          0,        # width
                                          0,        # height
                                          0,        # parent
                                          0,        # menu
                                          0,        # hInstance
                                          None      # lParam
                                          )
        # list of process handles to wait for                     
        handles = []
        # First time through add first process handle to list
        handles.append(self.needWaiting[processHandleKey])
        # Save window so IO thread can wake us up with it
        threadHandle = self.phandleKeyToThreadHandle[processHandleKey]
        self.threadToMsgWindow[threadHandle] = theWindow
        self.threadToNumEnded[threadHandle] = 0
        # Signal an event so IO thread knows that window
        # is successfully created so it can call PostMessage.
        # Note that this line is intentionally placed after setting
        # threadToMsgWindow so that we don't attempt to lookup a msg window
        # in the IO thread before defining it here.
        self.threadToMsgWindowCreated[threadHandle] = True
        SetEvent(self.threadToMsgWindowCreationEvent[threadHandle])
        
        while True:
            val = MsgWaitForMultipleObjects(handles, 0, INFINITE, QS_POSTMESSAGE | QS_ALLEVENTS)
            if val >= WAIT_OBJECT_0 and val < WAIT_OBJECT_0 + len(handles):
                phandle = handles[val - WAIT_OBJECT_0]
                # Remove process handle from wait list
                handles.remove(phandle)
                # Tell transport process ended
                transport = self.phandleToTransport[phandle]
                phandleKey = self.phandleToPhandleKey[phandle]
                self.reactor.callFromThread(self.processEnded, phandle, phandleKey)
            elif val == WAIT_OBJECT_0 + len(handles):
                # We were interrupted by the IO thread calling PostMessage
                status, msg = win32gui.PeekMessage(theWindow,
                                                   0,
                                                   0,
                                                   win32con.PM_REMOVE)
                while status != 0:
                    if msg[1] == WM_NEW_PHANDLE:
                        # Add a process handle to wait list
                        phandleKey = msg[2]
                        handles.append(self.needWaiting[phandleKey])
                    elif msg[1] == WM_CLOSE_THREAD:
                        # Return so thread will exit
                        return
                    else:
                        # Drop all other messages, since we receive all messages, not
                        # just WM_NEW_PHANDLE and WM_CLOSE_THREAD.
                        pass
                    
                    status, msg = win32gui.PeekMessage(
                            theWindow,
                            0,
                            0,
                            win32con.PM_REMOVE)
            else:
                raise Exception("MsgWaitForMultipleObjects returned unknown value: %s" % str(val))

    def processEnded(self, processHandle, processHandleKey):
        wfmoThread = self.phandleKeyToThreadHandle[processHandleKey]
        processTransport = self.phandleToTransport[processHandle]
        self.threadToNumEnded[wfmoThread] += 1
        # Decrement proc handle count for thread
        self.threadToNumProcessHandles[wfmoThread] -= 1
        # If we go from 63 to 62 phandles for the thread, mark it available.
        if self.threadToNumProcessHandles[wfmoThread] == 62:
            self.availableThreads.append(wfmoThread)
            self.usedThreads.remove(wfmoThread)
        # If we go to 0 phandles, end the thread
        elif self.threadToNumProcessHandles[wfmoThread] == 0:
            # Mark thread as unavailable
            self.availableThreads.remove(wfmoThread)
            # Notify the thread that it should exit.
            if not self.threadToMsgWindowCreated[wfmoThread]:
                val = WaitForSingleObject(self.threadToMsgWindowCreationEvent[wfmoThread], INFINITE)
                if val != WAIT_OBJECT_0:
                    raise RuntimeError("WaitForSingleObject returned %d.  It should only return %d" % (val, WAIT_OBJECT_0))
            # Notify the thread that it should wait on the process handle.
            win32api.PostMessage(
                    self.threadToMsgWindow[wfmoThread], # thread id
                    WM_CLOSE_THREAD, # message 
                    0, # wParam
                    0 # lParam
                    )
            
            # Cleanup thread resources
            del self.threadToNumProcessHandles[wfmoThread]
            del self.threadToMsgWindowCreated[wfmoThread]
            #del self.wfmoThread
        
        # Cleanup process handle resources
        del self.needWaiting[processHandleKey]
        del self.phandleToTransport[processHandle]
        # Call the transport's processEnded method
        processTransport.processEnded()

