using System;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Collections;
using csharpReactor;
using csharpReactor.interfaces;
// "existential" because "abstract" is a C# keyword ;)

namespace csharpReactor.existential {
	public class NotImplementedError : System.Exception {
		public NotImplementedError(String message) : base(message) {}
	}

	public class FileDescriptor : IReadWriteDescriptor, IConsumer, 
																IProducer, ITransport {

		private const int _bufferSize = 1024 * 8;
		protected bool _connected = false;
		protected bool _producerPaused = false;
		protected bool _disconnected = false;
		protected bool _disconnecting = false;
		protected IProducer _producer = null;
		protected IConsumer _consumer = null;
		protected StringBuilder _dataBuffer = new StringBuilder(_bufferSize);
		protected int _offset = 0;
		protected StringBuilder _tempDataBuffer = new StringBuilder(_bufferSize);
		protected int _tempDataLen = 0;
		protected Socket _socket = null;
		protected double _sessionNum = 0;
		protected ITransport _server = null;
		protected IAddress _client = null;

		/// <summary>
		/// the connection was lost
		/// 
		/// called when the connection on a selectable object has been lost
		/// it will be called whether the connection was closed explicitly
		/// or an exception occured, or the other side of the connection
		/// closed it first
		/// 
		/// clean up state here, but make sure to call back up to FileDescriptor
		/// </summary>
		/// <param name="reason">IConnectionLost object</param>
		public virtual void connectionLost(IConnectionLost reason) {
			_disconnected = true;
			_connected = false;
			if (_producer != null) {
				_producer.stopProducing();
				_producer = null;
			}
		}

		public virtual void writeSomeData(String data) {
			throw new NotImplementedError("you must override this in subclasses");
		}

		// -- IProducer ---
		
		public virtual void stopProducing() {}

		// -- ITransport ---

		public virtual IAddress client		{ get { return null; } }
		public virtual IProtocol protocol { get { return null; } }
		public virtual IPort server       { get { return null; } }
		public virtual double sessionNum  { get { return -1; } }
		public virtual bool connected     { get { return false; } }

		public virtual void startReading() {
			Reactor.instance.addReader(this);
		}

		// -- IConsumer ----
		public virtual void registerProducer(IProducer producer, bool streaming) {}
		public virtual void unregisterProducer() {}
		public virtual void write(String data) {
		}
		
		// -- IReadWriteDescriptor ---
		public virtual Socket socket			{ get { return null; } }

	}
}