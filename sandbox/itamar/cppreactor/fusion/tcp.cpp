#include <iostream>
#include <unistd.h>
#include <stdlib.h>
#include <limits.h>
#include <errno.h>
#include <assert.h>
#include <boost/python.hpp> 
using namespace boost::python;
#include "twisted/tcp.h"
#include "twisted/util.h"
using namespace Twisted;


namespace {
    object None = import("__builtin__").attr("None");
}

void TwistedImpl::IOVecManager::ensureEnoughSpace() 
{
    if (m_len > m_offset + m_used) {
	return;
    }
    // no slot at end, check if we can move
    if (m_offset > 128) {
	::memmove(m_vecs, m_vecs + m_offset, m_used);
	m_offset = 0;
    } else {
	// allocate more
	m_vecs = (iovec*) ::realloc(m_vecs, m_len + 2048);
	m_len += 2048;
    }
}


char* TwistedImpl::LocalBufferManager::getBuffer(size_t bytes)
{
    // first, make sure we have a buffer with sufficient 
    if (m_localbuffers.empty() || m_localbuffers.back().available() < bytes) {
	LocalBuffer b;
	b.numchunks = bytes / LocalBuffer::CHUNK_SIZE;
	if (bytes % LocalBuffer::CHUNK_SIZE)
	    b.numchunks++;
	b.offset = 0;
	b.len = 0;
	b.buf = (char*) new char[LocalBuffer::CHUNK_SIZE * b.numchunks];
	m_localbuffers.push_back(b);
    }
    LocalBuffer& b = m_localbuffers.back();
    b.len += bytes;
    return b.buf;
}

void TwistedImpl::LocalBufferManager::didntUse(size_t bytes)
{
    assert (!m_localbuffers.empty());
    LocalBuffer& b = m_localbuffers.back();
    assert (bytes <= b.len);
    b.len -= bytes;
}

void TwistedImpl::LocalBufferManager::freePartOfBuffer(size_t bytes)
{
    assert (!m_localbuffers.empty());
    LocalBuffer& b = m_localbuffers.front();
    assert (bytes <= b.len);
    b.len -= bytes;
    if (b.len == 0) {
	b.offset = 0;
	if (m_localbuffers.size() == 1)
	    return;
	if (m_localbuffers.back().available() > 0) {
	    delete[] b.buf;
	    m_localbuffers.pop_front();
	} else {
	    m_localbuffers.push_back(b);
	    m_localbuffers.pop_front();
	}
	return;
    } else {
	b.offset += bytes;
    }
}

TwistedImpl::LocalBufferManager::~LocalBufferManager()
{
    for (std::deque<LocalBuffer>::iterator it = m_localbuffers.begin();
	 it != m_localbuffers.end(); ++it) {
	delete[] it->buf;
    }
}

Twisted::TCPTransport::TCPTransport(object self) : 
    m_self(self), m_hasproducer(false), m_writable(false), 
    m_bufferedbytes(0), connected(0), producerPaused(0),
    streamingProducer(0), disconnecting(0) {}

void Twisted::TCPTransport::initProtocol()
{
    extract<Twisted::Protocol*> pchecker(m_self.attr("protocol"));
    if (pchecker.check()) {
	m_protocol = pchecker();
	if (m_protocol == NULL) {
	    // XXX throw exception.
	}
	m_protocol->init(object(m_self.attr("protocol")).ptr());
	m_sockfd = extract<int>(m_self.attr("fileno")());
    } else {
	m_protocol = 0;
    }
}

object Twisted::TCPTransport::doRead()
{
    if (m_protocol) {
	if (m_readbuflen == 0) {
	    m_protocol->bufferFull();
	    return None;
	}
	int result = ::read(m_sockfd, m_readbuffer, m_readbuflen);
	if (result == 0) {
	    return import("twisted.internet.main").attr("CONNECTION_DONE");
	} else if (result > 0) {
	    m_readbuffer += result;
	    m_readbuflen -= result;
	    m_protocol->dataReceived(m_readbuffer - result, result);
	} else if (result == EWOULDBLOCK) {
	    return None;
	} else {
	    return import("twisted.internet.main").attr("CONNECTION_LOST");
	}
    } else {
	return import("twisted.internet.tcp").attr("Connection").attr("doRead")(m_self);
    }
    return None;
}

object Twisted::TCPTransport::doWrite()
{
    if (!m_protocol) {
	return import("twisted.internet.tcp").attr("Connection").attr("doWrite")(m_self);
    }
    m_iovec.twiddleFirst();
    ssize_t result = ::writev(m_sockfd, m_iovec.m_vecs + m_iovec.m_offset, 
			  std::min(int(m_iovec.m_used), IOV_MAX));
    m_iovec.untwiddleFirst();
    if (result < 0) {
	if (errno == EINTR) {
	    return doWrite(); // try again
	} else if (errno == EWOULDBLOCK) {
	    return object(0);
	} else {
	    return import("twisted.internet.main").attr("CONNECTION_LOST");
	}
    }
    if (result > 0) {
	wrote(result);
    }
    if (m_bufferedbytes == 0) {
	assert (m_local.m_localbuffers.empty() || 
		m_local.localbuffers.front().len == 0);
	assert (m_iovec.m_used == 0);
	stopWriting();
	if (m_hasproducer && (!this->streamingProducer || this->producerPaused)) {
	    m_producer.attr("resumeProducing")();
	    this->producerPaused = true;
	} else if (this->disconnecting) {
	    return m_self.attr("_postLoseConnection")();
	}
    }
    return None;
}

void Twisted::TCPTransport::wrote(size_t bytes)
{
    if (bytes == 0)
	return;
    assert (bytes <= m_bufferedbytes);
    m_bufferedbytes -= bytes;
    if (m_iovec.m_bytessent) {
	bytes += m_iovec.m_bytessent;
	m_iovec.m_bytessent = 0;
    }
    while (bytes > 0) {
	iovec* vec = m_iovec.m_vecs + m_iovec.m_offset;
	if (vec->iov_len > bytes) {
	    m_iovec.m_bytessent = bytes;
	    return;
	}
	bytes -= vec->iov_len;
	m_iovec.m_offset++;
	m_iovec.m_used--;
	std::pair<bool,OwnerPtr> p = m_iovec.m_ownerqueue.front();
	m_iovec.m_ownerqueue.pop();
	if (!p.first) {
	    // local storage
	    m_local.freePartOfBuffer(vec->iov_len);
	}
    }
    assert (bytes == 0);
}


BOOST_PYTHON_MODULE(tcp)
{
    class_<TCPTransport>("TCPTransportMixin", init<object>())
	.def("initProtocol", &TCPTransport::initProtocol)
	.def("doRead", &TCPTransport::doRead)
	.def("doWrite", &TCPTransport::doWrite)
	.def("startWriting", &TCPTransport::startWriting)
	.def("stopWriting", &TCPTransport::stopWriting)
	.def_readwrite("connected", &TCPTransport::connected)
	.def_readwrite("disconnecting", &TCPTransport::disconnecting)
	.def_readwrite("producerPaused", &TCPTransport::producerPaused)
	.def_readwrite("streamingProducer", &TCPTransport::streamingProducer)
	.add_property("producer", &TCPTransport::_getProducer, &TCPTransport::_setProducer)
	;
    class_<Protocol, bases<>, boost::noncopyable>("Protocol", no_init)
	.def("connectionMade", &Protocol::connectionMade)
	.def("connectionLost", &Protocol::connectionLost)
	.def("makeConnection", &Protocol::makeConnection)
	.def_readonly("transport", &Protocol::transportobj)
	;
}
