using System;
using System.Net;
using System.Net.Sockets;
using CSReactor.Interfaces;

namespace CSReactor {

	public class Connection : ITCPTransport, ISystemHandle {
		Socket socket;
		IProtocol protocol;

		public Connection(Socket skt, IProtocol protocol) {
			this.socket = skt;
			this.protocol = protocol;		
		}
        
        protected void closeSocket() { 
        }
        
        public String logPrefix() {
            // TODO: implement logging ;)
        }
		
		public Socket getHandle(){
			return socket;
		}

		public bool getTcpNoDelay() {
			return socket.GetSocketOption(SocketOptionLevel.Tcp, SocketOptionName.NoDelay);
		}
		public void setTcpNoDelay(bool b) {
			socket.SetSocketOption(SocketOptionLevel.Tcp, SocketOptionName.NoDelay);
		}
		public bool getTcpKeepAlive() {
			return socket.GetSocketOption(SocketOptionLevel.Tcp, SocketOptionName.KeepAlive);
		}
		public void setTcpKeepAlive(bool b) {
			socket.GetSocketOption(SocketOptionLevel.Tcp, SocketOptionName.KeepAlive);
        }
	}

    public class Port {
#if false
		public void write(String data) {}
		public void write(String[] data) {}
		public void loseConnection() {
            
        }
#endif
    }
    public class BaseClient {
        public void connectionLost(String reason) {
        }

        protected Socket createInternetSocket() {
        }
        
        public void doConnect() {
        }

        public void failIfNotConnected(Exception err) {
        }

        public void stopConnecting() {
        }
    }

    public class Client : BaseClient {
		public IPEndPoint getPeer() {
			return (IPEndPoint)socket.RemoteEndPoint;
		}

		public IPEndPoint getHost() {
			return (IPEndPoint)socket.LocalEndPoint;
		}
    }

    public class Server {
        
    }

}
