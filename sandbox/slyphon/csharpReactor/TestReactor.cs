using System;
using System.Collections;
using System.Net;
using System.Net.Sockets;
using NUnit.Framework;
using NMock;
using csharpReactor.interfaces;

namespace csharpReactor.tests {
	[TestFixture]
	public class TestReactor {
		static IPAddress localhost = IPAddress.Parse("127.0.0.1");			
		// XXX: this is teh suck, figure out a way of getting an open 
		// port dynamically 
		static IPEndPoint ep = new IPEndPoint(localhost, 9999); 
		
		public Socket gimmeASocket() {
			return new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);	
		}

		[Test]
		public void testListenTCP() {
			Reactor r = Reactor.instance;
			DynamicMock mfactory = new DynamicMock(typeof(IFactory));
			IFactory f = (IFactory)mfactory.MockInstance;
			Object o = r.listenTCP(ep, f, 10);
			Assert.AreSame(o.GetType(), typeof(tcp.Port));
			ArrayList al = new ArrayList(r.removeAll());
			Assert.IsTrue(al.Count == 1);
		}

		[Test]
		public void testAddReader() {
			Reactor r = Reactor.instance;
			DynamicMock mock = new DynamicMock(typeof(ISocket));
			Socket s = gimmeASocket();
			mock.ExpectAndReturn("socket", s);
			r.addReader((ISocket) mock.MockInstance);
			mock.Verify();
			ArrayList al = new ArrayList(r.removeAll());
			Assert.IsTrue(al.Count == 1);
		}
		
		[Test]
		public void testServer() {
			Reactor r = Reactor.instance;
			DynamicMock proto = new DynamicMock(typeof(IProtocol));
			Socket sock = gimmeASocket();
			tcp.Server s = new tcp.Server(sock, (IProtocol)proto.MockInstance, 
														(IAddress)(new DynamicMock(typeof(IAddress))).MockInstance,
														(IListeningPort)(new DynamicMock(typeof(IListeningPort))).MockInstance,
														100);
			ArrayList reads = new ArrayList(r.removeAll());			
			Assert.IsTrue(reads.Count == 1);
		}

	}
}