using System;
using System.Net;
using System.Net.Sockets;
using System.Collections;
using csharpReactor.Collections;
using csharpReactor.interfaces;

namespace csharpReactor {
	/// <summary>
	/// Summary description for Reactor.
	/// </summary>
	public class Reactor : IReactor {
		private Hashtable _reads = new Hashtable();
		private Hashtable _writes = new Hashtable();
		private bool _running = false;
		private static Reactor _instance = null;

		private Reactor() {}

		public static Reactor instance {
			get {
				if (_instance == null) 
					_instance = new Reactor();
				return _instance;
			}
		}

		public Hashtable readables {
			get { return this._reads; }
		}
		
		public Hashtable writeables {
			get { return this._writes; }
		}

    public bool running {
      get { return this._running; }
    }

		public IListeningPort listenTCP(IPEndPoint endPoint, IFactory factory, int backlog) {
			tcp.Port p = new tcp.Port(endPoint, factory, backlog, this);
			p.startListening();
			return p;
		}

		public void doIteration(int timeout) {
			doSelect(timeout);
		}

		public void doSelect(int timeout) {
			ArrayList readers = new ArrayList(_reads.Keys);
			ArrayList writers = new ArrayList(_writes.Keys);

			Socket.Select(readers, writers, null, timeout);
			if (readers.Count > 0) {
				Console.WriteLine("we got a connectable socket!");
			}
		}
		
		public void addReader(ISocket fd) {
			this._reads.Add(fd.socket, fd);
		}
		
		public void removeReader(ISocket isock) {
			if (this._reads.ContainsKey(isock)) {
				this._reads.Remove(isock);
			}
		}

		public void addWriter(ISocket isock) {
			this._writes.Add(isock.socket, isock);
		}

		public void removeWriter(ISocket isock) {
			if (this._writes.ContainsKey(isock)) {
				this._writes.Remove(isock);
			}
		}

		public ICollection removeAll() {
			ArrayList values = new ArrayList(this._reads.Values);
			ArrayList keys = new ArrayList(this._reads.Keys);
			// this is kind of confusing, why would reads' keys hold true
			// for objects in writes?
			foreach (Object o in keys) {
				if (this._reads.ContainsKey(o))
					this._reads.Remove(o);
				if (this._writes.ContainsKey(o))
					this._writes.Remove(o);
			}
			return (ICollection)values;
		}

		public void run() {
			this._running = true;
			mainLoop();
		}

		public void stop() {
			this._running = false;
		}

		public void mainLoop() {
			Console.WriteLine("MainLoop running");
			while (this._running) {
				this.doSelect(100);
			}
		}

		public static void Main() { 
			Reactor r = new Reactor();
			r.listenTCP(new IPEndPoint(IPAddress.Parse("127.0.0.1"), 9999), new Factory(), 10);
			r.run();
		}
	}
}
