
_epoll.so:	_epoll.c
	gcc -Wall -I/usr/include/python2.3/ -lpython2.3 -shared _epoll.c -o _epoll.so

_epoll.c:	_epoll.pyx
	pyrexc _epoll.pyx

clean:
	rm -rf *.pyc _epoll.so _epoll.c
