using System;

namespace csharpReactor {
	public class Factory : IFactory {
		protected Type protocol;

		public System.Type Protocol {
			get { return this.protocol; }
			set { this.protocol = value; }
		}

		public virtual void doStart() {}
		public virtual void doStop() {}
		public virtual IProtocol buildProtocol() {
			return (IProtocol)System.Activator.CreateInstance(this.protocol);
		}
	}
}
