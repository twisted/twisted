using System;
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

		[Test]
		public void testListenTCP() {
			Reactor r = new Reactor();
			DynamicMock mfactory = new DynamicMock(typeof(IFactory));
			IFactory f = (IFactory)mfactory.MockInstance;
			Object o = r.listenTCP(ep, f, 10);
			Assert.AreSame(o.GetType(), typeof(Port));
		}

		[Test]
		public void testAddReader() {
			Reactor r = new Reactor();
			DynamicMock mock = new DynamicMock(typeof(IFileDescriptor));
			Socket s = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
			mock.ExpectAndReturn("selectableSocket", s);
			r.addReader((IFileDescriptor) mock.MockInstance);
			mock.Verify();
		}
	}
}