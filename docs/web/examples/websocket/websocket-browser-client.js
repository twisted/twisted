function recordEvent(evtType, evt) {
 const console = document.getElementById("console");
 const div = document.createElement("div");
 console.append(div);
 div.append(document.createTextNode(evtType + ": «" + evt + "»"));
}

function doConnect() {
 webSocket = new WebSocket("ws://localhost:8080/websocket-server.rpy");
 webSocket.onopen = (event) => {
  console.log("opened");
  webSocket.send("hello world");
  recordEvent("socket opened", JSON.stringify(event));
 };
 webSocket.onmessage = (event) => {
  recordEvent("message received", event.data)
 };
 webSocket.onerror = (event) => {
  recordEvent("error", JSON.stringify(event));
 };
 webSocket.onclose = (event) => {
  recordEvent("close", JSON.stringify(event));
 };
}
