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

		public Hashtable readables {
			get { return this._reads; }
		}
		
		public Hashtable writeables {
			get { return this._writes; }
		}

    public bool running {
      get { return this._running; }
    }

		public IPort listenTCP(IPEndPoint endPoint, IFactory factory, int backlog) {
			Port p = new Port(endPoint, factory, backlog, this);
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
		
		public void addReader(IFileDescriptor fd) {
			this._reads.Add(fd.selectableSocket, fd);
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
