using System;
using System.Net;
using System.Net.Sockets;
using csharpReactor.interfaces;

namespace csharpReactor {
	/// <summary>
	/// I represent an IPv4 socket endpoint
	/// </summary>
	public class Address : IAddress {
		protected ProtocolType _ptype;
		protected IPEndPoint _endPoint = null;

		public Address(ProtocolType ptype, IPEndPoint ep) {
			this._ptype = ptype;
			this._endPoint = ep;
		}
		
		/// <summary>
		/// generate an Address object given a Socket. Will 
		/// use the values of the RemoteEndPoint
		/// </summary>
		/// <param name="s"></param>
		public Address(Socket s) {
			this._ptype = s.ProtocolType;
			this._endPoint = (IPEndPoint)s.RemoteEndPoint;
		}

		public ProtocolType protocolType {
			get { return this._ptype; }
			set { this._ptype = value; }
		}

		public int port {
			get { return this._endPoint.Port; }
			set { this._endPoint.Port = value; }
		}

		public IPAddress ipAddress {
			get { return this._endPoint.Address; }
			set { this._endPoint.Address = value; }
		}
	}
}
