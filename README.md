# FloraServer
通过继承大量修改 websocket-server 库类自定义网络路由器, 分流普通 HTTP 连接与 WebSocket 连接, 并且构造 WSGI 环境与 HTTP 请求头调用 flask, 实现 websocket-server 与 flask 共用一个端口通信
