using System;
using System.Net;

namespace csharpReactor {
	public class Protocol {
		protected bool connected = false;
		protected IFactory factory;
		protected IPEndPoint address = null;
		
		public Protocol() : this(null, null) {}

		public Protocol(IPEndPoint address) : this(address, null) {
		}

		public Protocol(IPEndPoint address, IFactory factory) {
			this.address = address;
			this.factory = factory;
		}

		public bool Connected {
			get { return this.connected; }
		}
		
		public IFactory Factory {
			get { return this.factory; }
			set { this.factory = value; }
		}

		public virtual void makeConnection() {
			this.connected = true;
			this.connectionMade();
		}

		public virtual void connectionMade() {}
		public virtual void connectionLost(IConnectionLost reason) {}
		public virtual void dataReceived(String data) {}
	}

}
