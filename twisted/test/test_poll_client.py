# -*- coding: utf-8 -*-

import socket
import time
import os

HOST = '127.0.0.1'
PORT = 9529

conns = []
def do_run_cycle():
  i = 0
  while 1:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if not s:
      print "can not create socket"
      continue
    s.settimeout(20)
    s.connect((HOST, PORT))
    conns.append(s)
    i += 1
    if i >= 10000:
      break
    print 'done connection ', i

if __name__ == '__main__':
  do_run_cycle()
  time.sleep(1)
  del conns

