using System;
using System.Text;
using System.Net;
using System.Net.Sockets;
using System.Collections;
using csharpReactor;
using csharpReactor.interfaces;
using csharpReactor.misc;

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
		protected double _sessionNum = 0;
		protected Socket _socket = null;

		protected bool _streamingProducer = false;
		protected IProducer _producer = null;
		protected IConsumer _consumer = null;
		protected int _offset = 0;
		protected StringBuilder _dataBuffer = new StringBuilder(_bufferSize);

		protected int _tempDataLen = 0;
		protected StringBuilder _tempDataBuffer = new StringBuilder(_bufferSize);

		protected IListeningPort _server = null;
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

		private void notImplemented() {
			throw new NotImplementedError("you must override this in subclasses");
		}

		/// <summary>
		/// "Write as much as possible of the given data, immediately.
		/// This is called to invoke the lower-level writing functionality, such as
		/// a socket's send() method, or a file's write(); this method returns an
		/// integer.  If positive, it is the number of bytes written; if negative,
		/// it indicates the connection was lost.
		/// </summary>
		/// <param name="data">The data to write</param>
		public virtual int writeSomeData(String data) { notImplemented(); return 0;}

		public virtual void startReading() {
			Reactor.instance.addReader(this);
		}

		public virtual void stopReading() {
			Reactor.instance.removeReader(this);
		}

		public virtual void startWriting() { 
			Reactor.instance.addWriter(this);
		}

		public virtual void stopWriting() { 
			Reactor.instance.removeWriter(this);
		}

		// -- IProducer ---
		
		public virtual void stopProducing() {}
		public virtual void pauseProducing() {}
		public virtual void resumeProducing() {}

		// -- ITransport ---
		public virtual double sessionNum  { get { return this._sessionNum; } }
		public virtual bool connected     { get { return this._connected; } }

		public virtual IAddress getPeer() {	notImplemented();	return null; }
		public virtual IAddress getHost() { notImplemented(); return null; }

		public virtual void loseConnection() {
			if (this._connected) {
				stopReading();
				startWriting();
				_disconnecting = true;
			}
		}

		// -- IConsumer ----
		public virtual void registerProducer(IProducer producer, bool streaming) {
      if (this._producer != null) {

      }
    }

		public virtual void unregisterProducer() {}

		public virtual void write(String data) {
			// somehow make sure that data is not unicode
			if (!this._connected) 
				return;
			if (data != null) {
				_tempDataBuffer.Append(data);
				if ((_producer != null) && 
					(_dataBuffer.Length + _tempDataBuffer.Length > _bufferSize)) {
					this._producerPaused = true;
					this._producer.pauseProducing();
				}
				startWriting();
			}
		}

		
		// -- IReadWriteDescriptor ---
		public virtual Socket socket { get { return this._socket; } }

		/// <summary>
		/// Called when data is available for writing.
		///  
		/// A result that is true (which will be a negative number) implies the
		/// connection was lost. A false result implies the connection is still
		/// there; a result of 0 implies no write was done, and a result of None
		/// indicates that a write was done. 
		/// </summary>
		/// <returns>A >
		public virtual Nullable<int> doWrite() {
			_dataBuffer.Append(_tempDataBuffer.ToString());
			_tempDataBuffer = new StringBuilder();
			
			int L = 0;
      Nullable<int> result = new Nullable<int>();

			if (_offset > 0) {
				L = writeSomeData(_dataBuffer.ToString(_offset, _dataBuffer.Length));
			} else {
				L = writeSomeData(_dataBuffer.ToString());
			}
			
			if (L < 0) {  // line 94 of t.i.abstract has a check for an Exception
				result.Value = L;
        return result;
      }
			if (L == 0 && _dataBuffer.Length > 0) // XXX: this may be wrong
              //XXX: WRONG! this should be a nullable
				result.Value = 0;
			
			_offset += L;
			
			// if there is nothing left to send
			if (_offset == _dataBuffer.Length) {
				_dataBuffer = new StringBuilder(_bufferSize);
				_offset = 0;
				// stop writing
				stopWriting();
				// if i have a producer who's supposed to supply me with data
				if ((_producer != null) && ((!_streamingProducer) || _producerPaused)) {
					_producer.resumeProducing();
					_producerPaused = false;
				} else if (_disconnecting) {
					// XXX: This is kind of screwed. should be able to return int or
					// main.CONNECTION_DONE :/
					// perhaps should raise ConnectionDone?
					notImplemented();
				}
			}
			return result;
		}

		public virtual void doRead() { notImplemented(); }
		public virtual void writeSequence(String[] data) { notImplemented(); }
	}
}
