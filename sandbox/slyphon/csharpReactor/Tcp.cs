using System;
using System.Net;
using System.Net.Sockets;

namespace csharpReactor {
	public class Server : ITransport {
		protected Socket _sock;
		protected IProtocol _proto;
		protected IAddress _client;
		protected IPort _server;
		protected double _sessionNum;
		protected bool _connected = false;

		public Server(Socket sock, IProtocol p, IAddress client, IPort server, double sessionNum) {
			this._sock = sock;
			this._proto = p;
			this._client = client;
			this._server = server;
			this._sessionNum = sessionNum;
			// TODO: figure out logging code at some point and put default logstr here
			startReading();
			this._connected = true;
		}

		public void startReading() {

		}
	}

	public class Port : IFileDescriptor, IPort {
		public static AddressFamily addressFamily = AddressFamily.InterNetwork;
		public static SocketType socketType = SocketType.Stream;
		public static ProtocolType protocolType = ProtocolType.Tcp;
		protected IPEndPoint localEndPoint;
		protected IFactory factory;
		protected int backlog;
		protected Socket socket; // the listening socket
		protected Address address;
		protected bool connected = false;
		protected int numberAccepts = 100;
		protected double sessionNum = 0;
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
			this.address = new Address(protocolType, localEndPoint);
		}

		/// <summary>
		/// called when my socket is ready for reading!
		/// accept a connection and sets up the protocol
		/// </summary>
		public void doRead() {
			Socket s = this.socket.Accept();
			IProtocol p = this.factory.buildProtocol(new Address(s));
			if (p == null) {
				s.Close(); // reject the connection attempt
			} else {
				this.sessionNum++; // XXX: Should probably be concerned about rollover
				ITransport transport = new Server(s, p, new Address(s), (IPort)this, this.sessionNum);
				p.makeConnection(transport);
			}
		}

		/// <summary>
		/// return a socket suitable for Select()ing on
		/// </summary>
		public Socket selectableSocket {
			get { return this.socket; }
		}

		public Socket createInternetSocket() {
			Socket s = new Socket(addressFamily, socketType, protocolType);
			s.Blocking = false;
			this.socket = s;
			return s;
		}
		
		public void startReading() {
			this.reactor.addReader(this);
		}

		/// <summary>
		/// Create and bind my socket, and begin listening on it
		/// </summary>
		public void startListening() {
			Socket skt = createInternetSocket();
			skt.Bind(localEndPoint);
			this.factory.doStart();
			skt.Listen(backlog);
			this.connected = true;
			this.socket = skt;
			startReading();
		}
	}
}
