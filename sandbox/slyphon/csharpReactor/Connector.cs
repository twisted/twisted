using System;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace csharpReactor {
	/// <summary>
	/// Summary description for Connector.
	/// </summary>
#if false
	public class Connector : IConnector {
		protected IFactory factory;
		protected int timeout;
		protected IReactor reactor; 
		protected Socket listeningSocket; // a socket listening for connections

		public Socket ListeningSocket {
			get { return this.listSocket; }
			set { this.listSocket = value; }
		}

		public IPEndPoint BindAddress {
			get { return (IPEndPoint)listeningSocket.LocalEndPoint; }
		}

		public IPEndPoint Peer {
			get { return (IPEndPoint)listeningSocket.RemoteEndPoint; }
		}

		public Connector(Socket listSocket, IFactory factory, int timeout, IReactor reactor) {
			this.listSocket = listSocket;
			this.factory = factory;
			this.timeout = timeout;
			this.reactor = reactor;
		}      
	}
#endif

}

