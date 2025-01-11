# OneBot 服务中继

> 用于将多个服务端对接到 Onebot 协议端

**当前仅适用于 正向 WebSocket 连接**

## 使用方法

```bash
uv sync
uv run main.py
```

Onebot协议端使用正向WS

填写 `app.yaml` 中 `to.host` 和 `to.port` 字段，分别填写服务端的 WebSocket 地址和端口

填写 `server.host` 和 `server.port` 字段，分别填写此服务绑定的 WebSocket 地址和端口

服务端使用 `ws://{server.host}:{server.port}` 发起 WebSocket 连接
