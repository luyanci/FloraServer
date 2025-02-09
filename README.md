## Language
* **`简体中文`**
* **[`English`](./README_EN.md)**
# FloraServer
**通过继承大量修改 `websocket-server` 库类自定义网络路由器, 分流普通 `HTTP` 连接与 `WebSocket` 连接, 并且构造 `WSGI` 环境与 `HTTP` 请求头调用 `flask`, 实现 `websocket-server` 与 `flask` 共用一个端口通信**
# 如何使用?
1. **~~你可以选择直接 `clone` 本仓库至您的项目中~~**
2. **或者使用以下指令安装**
```Shell
pip install FloraServer
```
3. **将 `FloraServer` 导入至您的项目中, `from FloraServer import [类]`**
**本项目有两个 `WebSocketServer类`, 一个是 `FloraFlaskWSServer`, 本仓库的主角, 另一个是 `FloraWebsocketServer`, 与 `WebsocketServer` 并无太大区别, 只是连接比较宽松而已**  
4. **开始使用, 按照 `flask` 和 `websocket-server` 开发文档使用即可**
## 代码示范
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
