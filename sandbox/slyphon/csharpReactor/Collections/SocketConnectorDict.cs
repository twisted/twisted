using System;
using System.Net;
using csharpReactor;
using System.Collections;

namespace csharpReactor.Collections {
	public class SocketConnectorDict : IDictionary, ICollection, IEnumerable, ICloneable {
		protected Hashtable innerHash;
		
		#region "Constructors"
		public  SocketConnectorDict() {
			innerHash = new Hashtable();
		}
		
		public SocketConnectorDict(SocketConnectorDict original) {
			innerHash = new Hashtable (original.innerHash);
		}
		
		public SocketConnectorDict(IDictionary dictionary) {
			innerHash = new Hashtable (dictionary);
		}
		
		public SocketConnectorDict(int capacity) {
			innerHash = new Hashtable(capacity);
		}
		
		public SocketConnectorDict(IDictionary dictionary, float loadFactor) {
			innerHash = new Hashtable(dictionary, loadFactor);
		}
		
		public SocketConnectorDict(IHashCodeProvider codeProvider, IComparer comparer) {
			innerHash = new Hashtable (codeProvider, comparer);
		}
		
		public SocketConnectorDict(int capacity, int loadFactor) {
			innerHash = new Hashtable(capacity, loadFactor);
		}
		
		public SocketConnectorDict(IDictionary dictionary, IHashCodeProvider codeProvider, IComparer comparer) {
			innerHash = new Hashtable (dictionary, codeProvider, comparer);
		}
		
		public SocketConnectorDict(int capacity, IHashCodeProvider codeProvider, IComparer comparer) {
			innerHash = new Hashtable (capacity, codeProvider, comparer);
		}
		
		public SocketConnectorDict(IDictionary dictionary, float loadFactor, IHashCodeProvider codeProvider, IComparer comparer) {
			innerHash = new Hashtable (dictionary, loadFactor, codeProvider, comparer);
		}
		
		public SocketConnectorDict(int capacity, float loadFactor, IHashCodeProvider codeProvider, IComparer comparer) {
			innerHash = new Hashtable (capacity, loadFactor, codeProvider, comparer);
		}
		#endregion

		#region Implementation of IDictionary
		public SocketConnectorDictEnumerator GetEnumerator() {
			return new SocketConnectorDictEnumerator(this);
		}
        	
		System.Collections.IDictionaryEnumerator IDictionary.GetEnumerator() {
			return new SocketConnectorDictEnumerator(this);
		}
		
		IEnumerator IEnumerable.GetEnumerator() {
			return GetEnumerator();
		}
		
		public void Remove(System.Net.Sockets.Socket key) {
			innerHash.Remove (key);
		}
		
		void IDictionary.Remove(object key) {
			Remove ((System.Net.Sockets.Socket)key);
		}
		
		public bool Contains(System.Net.Sockets.Socket key) {
			return innerHash.Contains(key);
		}
		
		bool IDictionary.Contains(object key) {
			return Contains((System.Net.Sockets.Socket)key);
		}
		
		public void Clear() {
			innerHash.Clear();		
		}
		
		public void Add(System.Net.Sockets.Socket key, IConnector value) {
			innerHash.Add (key, value);
		}
		
		void IDictionary.Add(object key, object value) {
			Add ((System.Net.Sockets.Socket)key, (IConnector)value);
		}
		
		public bool IsReadOnly {
			get {
				return innerHash.IsReadOnly;
			}
		}
		
		public IConnector this[System.Net.Sockets.Socket key] {
			get {
				return (IConnector) innerHash[key];
			}
			set {
				innerHash[key] = value;
			}
		}
		
		object IDictionary.this[object key] {
			get {
				return this[(System.Net.Sockets.Socket)key];
			}
			set {
				this[(System.Net.Sockets.Socket)key] = (IConnector)value;
			}
		}
        	
		public System.Collections.ICollection Values {
			get {
				return innerHash.Values;
			}
		}
		
		public System.Collections.ICollection Keys {
			get {
				return innerHash.Keys;
			}
		}
		
		public bool IsFixedSize {
			get {
				return innerHash.IsFixedSize;
			}
		}
		#endregion
		
		#region Implementation of ICollection
		public void CopyTo(System.Array array, int index) {
			innerHash.CopyTo (array, index);
		}
		
		public bool IsSynchronized {
			get {
				return innerHash.IsSynchronized;
			}
		}
		
		public int Count {
			get {
				return innerHash.Count;
			}
		}
		
		public object SyncRoot {
			get {
				return innerHash.SyncRoot;
			}
		}
		#endregion
		
		#region Implementation of ICloneable
		public SocketConnectorDict Clone() {
			SocketConnectorDict clone = new SocketConnectorDict();
			clone.innerHash = (Hashtable) innerHash.Clone();
			
			return clone;
		}
		
		object ICloneable.Clone() {
			return Clone();
		}
		#endregion
		
		#region "HashTable Methods"
		public bool ContainsKey (System.Net.Sockets.Socket key) {
			return innerHash.ContainsKey(key);
		}
		
		public bool ContainsValue (IConnector value) {
			return innerHash.ContainsValue(value);
		}
		
		public static SocketConnectorDict Synchronized(SocketConnectorDict nonSync) {
			SocketConnectorDict sync = new SocketConnectorDict();
			sync.innerHash = Hashtable.Synchronized(nonSync.innerHash);

			return sync;
		}
		#endregion

		internal Hashtable InnerHash {
			get {
				return innerHash;
			}
		}
	}
	
	public class SocketConnectorDictEnumerator : IDictionaryEnumerator {
		private IDictionaryEnumerator innerEnumerator;
		
		internal SocketConnectorDictEnumerator (SocketConnectorDict enumerable) {
			innerEnumerator = enumerable.InnerHash.GetEnumerator();
		}
		
		#region Implementation of IDictionaryEnumerator
		public System.Net.Sockets.Socket Key {
			get {
				return (System.Net.Sockets.Socket)innerEnumerator.Key;
			}
		}
		
		object IDictionaryEnumerator.Key {
			get {
				return Key;
			}
		}
		
		public IConnector Value {
			get {
				return (IConnector)innerEnumerator.Value;
			}
		}
		
		object IDictionaryEnumerator.Value {
			get {
				return Value;
			}
		}
		
		public System.Collections.DictionaryEntry Entry {
			get {
				return innerEnumerator.Entry;
			}
		}
		#endregion
		
		#region Implementation of IEnumerator
		public void Reset() {
			innerEnumerator.Reset();
		}
		
		public bool MoveNext() {
			return innerEnumerator.MoveNext();
		}
		
		public object Current {
			get {
				return innerEnumerator.Current;
			}
		}
		#endregion
	}
}
