using System;
using System.Net;
using System.Net.Sockets;

namespace csharpReactor {
	public class Port : IFileDescriptor {
		public static AddressFamily addressFamily = AddressFamily.InterNetwork;
		public static SocketType socketType = SocketType.Stream;
		public static ProtocolType protocolType = ProtocolType.Tcp;
		protected IPEndPoint localEndPoint;
		protected IFactory factory;
		protected int backlog;
		protected Socket socket; // the listening socket
		protected bool connected = false;
		protected int numberAccepts = 100;
		protected IReactor reactor;

		/// <summary>
		/// I am a TCP server port, listening for connections
		/// </summary>
		/// <param name="localEndPoint">the local end point to bind to</param>
		/// <param name="factory">the IFactory object I will use to create protocol instances with</param>
		/// <param name="backlog">number of backlogged connections to keep queued</param>
		/// <param name="reactor"></param>
		public Port(IPEndPoint localEndPoint, IFactory factory, int backlog, IReactor reactor) { // not sure how to handle "interface" on win32
			this.localEndPoint = localEndPoint;
			this.factory = factory;
			this.backlog = backlog;
			this.reactor = reactor;
		}

		public void DoRead() {
			
		}

		public Socket SelectableSocket {
			get { return this.socket; }
		}

		public Socket CreateInternetSocket() {
			Socket s = new Socket(addressFamily, socketType, protocolType);
			s.Blocking = false;
			this.socket = s;
			return s;
		}
		
		public void StartReading() {
			this.reactor.AddReader(this);
		}

		/// <summary>
		/// Create and bind my socket, and begin listening on it
		/// </summary>
		public void StartListening() {
			Socket skt = CreateInternetSocket();
			skt.Bind(localEndPoint);
			this.factory.DoStart();
			skt.Listen(backlog);
			this.connected = true;
			this.socket = skt;
			StartReading();
		}
	}
}