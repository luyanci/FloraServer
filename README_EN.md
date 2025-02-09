# FloraServer
**By inheriting a large number of modified `websocket-server` library classes to customize a network router, splitting regular `HTTP` connections from `WebSocket` connections, and constructing a `WSGI` environment and `HTTP` request headers to call `flask`, `websocket-server` and `flask` can communicate on the same port**
# How to use it?
1. **You can choose to directly 'clone' this repository into your project**
2. **Or use the following command to install**
```Shell
pip install FloraServer
```
3. **Import `FloraServer` into your project `From FloraServer import [class]`**
**There are two `WebSocketServer classes` in this project, one is `FloraFlaskWSServer`, the protagonist of this repository, and the other is `FloraWebsocket Server`, which is not much different from `Websocket Server`, only with relatively loose connections**  
4. **To start using, follow the development documentation for `flask` and `websocket-server`**
## Code Demonstration
```Python
from FloraServer import FloraFlaskWSServer
from flask import Flask

app = Flask(__name__)

@app.route("/")
def index():
    return "Hello world!"


def on_message(client, server, message):
    print(message)


if __name__ == "__main__":
    server = FloraFlaskWSServer(flask_app=app, host="0.0.0.0", port=5000)
    server.set_fn_message_received(on_message)
    server.run_forever()
```
