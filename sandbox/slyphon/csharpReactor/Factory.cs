using System;
using csharpReactor.interfaces;

namespace csharpReactor {
	public class Factory : IFactory {
		protected Type _protocol;

		public System.Type protocol {
			get { return this._protocol; }
			set { this._protocol = value; }
		}

		public virtual void doStart() {}
		public virtual void doStop() {}
		public virtual IProtocol buildProtocol(IAddress addr) {
			return (IProtocol)System.Activator.CreateInstance(this.protocol);
		}
	}
}
