
cdef extern from "stdio.h":
	cdef extern void *malloc(int)
	cdef extern void free(void *)

cdef extern from "errno.h":
	cdef extern int errno

cdef extern from "string.h":
	cdef extern void *memset(void* s, int c, int n)

cdef enum:
	EPOLL_CTL_ADD = 1
	EPOLL_CTL_DEL = 2
	EPOLL_CTL_MOD = 3

cdef enum EPOLL_EVENTS:
	EPOLLIN = 0x001
	EPOLLPRI = 0x002
	EPOLLOUT = 0x004
	EPOLLRDNORM = 0x040
	EPOLLRDBAND = 0x080
	EPOLLWRNORM = 0x100
	EPOLLWRBAND = 0x200
	EPOLLMSG = 0x400
	EPOLLERR = 0x008
	EPOLLHUP = 0x010
	EPOLLET = (1 << 31)

cdef extern from "sys/epoll.h":
	ctypedef unsigned long uint32_t
	ctypedef unsigned long long uint64_t

	ctypedef union epoll_data_t:
		void *ptr
		int fd
		uint32_t u32
		uint64_t u64

	cdef struct epoll_event:
		uint32_t events
		epoll_data_t data

	int epoll_create(int size)
	int epoll_ctl(int epfd, int op, int fd, epoll_event *event)
	int epoll_wait(int epfd, epoll_event *events, int maxevents, int timeout)

import os

cdef class epoll:
	cdef int fd
	cdef int initialized

	def __init__(self, int size):
		self.fd = epoll_create(size)
		if self.fd == -1:
			raise OSError(errno, os.strerror(errno))
		self.initialized = 1

	def __dealloc__(self):
		if self.initialized:
			os.close(self.fd)
			self.initialized = 0

	def close(self):
		if self.initialized:
			os.close(self.fd)
			self.initialized = 0

	def control(self, int op, int fd, int events):
		cdef int result
		cdef epoll_event evt
		evt.events = events
		result = epoll_ctl(self.fd, op, fd, &evt)
		if result == -1:
			raise OSError(errno, os.strerror(errno))

	def wait(self, unsigned int maxevents, int timeout):
		cdef epoll_event *events
		cdef int result
		cdef int nbytes

		nbytes = sizeof(epoll_event) * maxevents
		events = <epoll_event*>malloc(nbytes)
		memset(events, 0, nbytes)
		try:
			result = epoll_wait(self.fd, events, maxevents, timeout)
			if result == -1:
				raise IOError(result, os.strerror(result))
			results = []
			for i from 0 <= i < result:
				results.append((events[i].data.fd, events[i].events))
			return results
		finally:
			free(events)

CTL_ADD = EPOLL_CTL_ADD
CTL_DEL = EPOLL_CTL_DEL
CTL_MOD = EPOLL_CTL_MOD

IN = EPOLLIN
PRI = EPOLLPRI
OUT = EPOLLOUT
RDNORM = EPOLLRDNORM
RDBAND = EPOLLRDBAND
WRNORM = EPOLLWRNORM
WRBAND = EPOLLWRBAND
MSG = EPOLLMSG
ERR = EPOLLERR
HUP = EPOLLHUP
ET = EPOLLET
