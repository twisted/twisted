using System;

namespace csharpReactor {
	public class Factory : IFactory {
		protected Type protocol;

		public System.Type Protocol {
			get { return this.protocol; }
			set { this.protocol = value; }
		}

		public virtual void DoStart() {}
		public virtual void DoStop() {}
		public virtual IProtocol BuildProtocol() {
			return (IProtocol)System.Activator.CreateInstance(this.protocol);
		}
	}
}
