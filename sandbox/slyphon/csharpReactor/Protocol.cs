using System;
using System.Net;

namespace csharpReactor {
	public class Protocol {
		protected bool _connected = false;
		protected IFactory _factory;
		protected IPEndPoint _address = null;
		protected ITransport _transport = null;

		public Protocol() : this(null, null) {}

		public Protocol(IPEndPoint address) : this(address, null) {
		}

		public Protocol(IPEndPoint address, IFactory factory) {
			this._address = address;
			this._factory = factory;
		}

		public virtual bool Connected {
			get { return this._connected; }
		}
		
		public virtual IFactory Factory {
			get { return this._factory; }
			set { this._factory = value; }
		}

		public virtual ITransport transport {
			get { return this._transport; }
		}

		public virtual void makeConnection(ITransport t) {
			this._connected = true;
			this._transport = t;
			this.connectionMade();
		}

		public virtual void connectionMade() {}
		public virtual void connectionLost(IConnectionLost reason) {}
		public virtual void dataReceived(String data) {}
	}

}
