using System;
using System.Net;
using System.Net.Sockets;
using System.Collections;

namespace CSReactor {
	namespace Interfaces{
		public interface ISystemHandle {
			Object getHandle();
		}

		// TODO: create IAddress 
		public interface IAddress {}
		
		// XXX: Need to define IFactory
		public interface IFactory {} 
		
		public interface IConnector {
			void stopConnecting();
			void disconnect();
			void connect();
			IAddress getDestination();
		}
		public interface ITransport {
			void write(String data);
			void write(String[] data);
			void loseConnection();
			// define IAddress!
			IPEndPoint getPeer();
			IPEndPoint getHost();
		}
		public interface ITCPTransport : ITransport {
			bool getTcpNoDelay();
			void setTcpNoDelay(bool b);
			bool getTcpKeepAlive();
			void setTcpKeepAlive(bool b);
		}
		public interface IProducer {
			void stopProducing();		
		}
		public interface IConsumer {
			void registerProducer(IProducer producer, bool streaming);
			void unregisterProducer();
			void write(String data);
		}
		public interface IProtocol {
			void dataReceived(String data);
			void connectionLost(System.Exception e);
			void makeConnection(ITransport transport);
			void connectionMade();
		}
		public interface IProtocolFactory {
			IProtocol buildProtocol(IAddress addr);
			void doStart();
			void doStop();
		}
		public interface IReadDescriptor {
			void doRead();
		}
		public interface IWriteDescriptor {
			void doWrite();
		}
		public interface IReadWriteDescriptor : IReadDescriptor, IWriteDescriptor {
		}
		public interface IListeningPort {
			void startListening();
			IAsyncResult stopListening();
			IAddress getHost();
		}
		public interface IReactorCore {
			IAsyncResult resolve(String name, double timeout);
			IAsyncResult resolve(String name, uint timeout);
			void run();
			void stop();
			void crash();
			void iterate(float delay);
			void iterate(System.UInt32 delay);
			void fireSystemEvent(String eventType);
			ulong addSystemEventTrigger(); //XXX: don't know how delegates work
			void removeSystemEventTrigger(ulong triggerID);
			ulong callWhenRunning();
		}
		public interface IReactorTCP {
			IListeningPort listenTCP(int port, IFactory factory, uint backlog); // interface?
			IConnector connectTCP(String hostName, uint port, IFactory factory, uint timeout); //bindAddress?
		}
	}
}
