#!/usr/bin/env python

import glob, os, signal, sys, time, unittest
sys.path.insert(0, glob.glob('build/lib.*'))
import event

class EventTest(unittest.TestCase):
    def setUp(self):
        event.init()

    def __timeout_cb(self, ev, handle, evtype, ts):
        now = time.time()
        self.failUnless(int(now - ts['start']) == ts['secs'],
                        'timeout event failed')
    
    def test_timeout(self):
        ts = { 'start':time.time(), 'secs':5 }
        ev = event.event(self.__timeout_cb, arg=ts)
        ev.add(ts['secs'])
        event.dispatch()

    def __signal_cb(self, ev, sig, evtype, arg):
        if evtype == event.EV_SIGNAL:
            ev.delete()
        elif evtype == event.EV_TIMEOUT:
            os.kill(os.getpid(), signal.SIGUSR1)
    
    def test_signal(self):
        event.add(event.event(self.__signal_cb, handle=signal.SIGUSR1,
                              evtype=event.EV_SIGNAL))
        event.add(event.event(self.__signal_cb), 2)
        event.dispatch()

    def __read_cb(self, ev, fd, evtype, pipe):
        buf = os.read(fd, 1024)
        self.failUnless(buf == 'hi niels', 'read event failed')
    
    def test_read(self):
        pipe = os.pipe()
        event.add(event.event(self.__read_cb, handle=pipe[0],
                              evtype=event.EV_READ))
        os.write(pipe[1], 'hi niels')
        event.dispatch()

if __name__ == '__main__':
    unittest.main()
