using System;
using System.Net;
using System.Net.Sockets;
using System.Text;

namespace csharpReactor {
	/// <summary>
	/// Summary description for Connector.
	/// </summary>
	public class Connector : IConnector {
		protected IFactory factory;
		protected int timeout;
		protected IReactor reactor;
		protected Socket sock;
		protected IProtocol protocol;
		private static int BUF_SIZE = 8192;
		private byte[] readBuffer = new byte[BUF_SIZE];

		public Socket SockHandle {
			get { return this.sock; }
		}

		public IPEndPoint BindAddress {
			get { return (IPEndPoint)sock.LocalEndPoint; }
		}

		public IPEndPoint Peer {
			get { return (IPEndPoint)sock.RemoteEndPoint; }
		}

		public Connector(Socket socket, IFactory factory, int timeout, IReactor reactor) {
			this.sock = socket;
			this.factory = factory;
			this.timeout = timeout;
			this.reactor = reactor;
		}
    
		private IAsyncResult SetupRead() {
			for (int i=0; i < readBuffer.Length; i++) {
				readBuffer[i] = 0;
			}
			return sock.BeginReceive(this.readBuffer, 0, BUF_SIZE, SocketFlags.None,
				new AsyncCallback(this.DoRead), this);
		}

		public void DoRead(IAsyncResult ar) {
			sock.EndReceive(ar);
			StringBuilder sb = new StringBuilder(BUF_SIZE);
			for (int i=0; i < readBuffer.Length; i++) {
				sb.Append(Convert.ToChar(sb[i]));
			}
			protocol.dataReceived(sb.ToString());
			SetupRead();
		}

		public void DoConnect(IAsyncResult ar) {
			Socket listener = (Socket)ar.AsyncState;
			Socket sock = listener.EndAccept(ar);
			protocol = (IProtocol) factory.buildProtocol();
			SetupRead();
		}  
	}
}

