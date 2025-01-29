# OneBot 服务中继

> 用于将多个服务端对接到 Onebot 协议端

**当前仅适用于 正向 WebSocket 连接**

## 使用方法

```bash
uv sync
uv run main.py
```

## 配置文件示例

`app.yaml`

```yaml
server:  # 必填，服务配置
  host: 0.0.0.0
  port: 8080
to:  # 必填，目标服务配置
  host: 0.0.0.0
  port: 8080
dead_check: 40 # 可选，心跳检测间隔配置
logger:   # 可选，日志级别配置
  level: 
    console: info
    file: warning
blacklist: []  # 可选，黑名单配置
whitelist: []  # 可选，白名单配置
notice:  # 可选，邮件通知配置，默认关闭
  smtp: smtp.example.com
  port: 465
  sender: example
  password: password
  receiver: example@example.com
  mail:  # 可选，邮件模板配置
    title: 你的Bot掉线了
    subject: OneBot 掉线通知
    content: OneBot 掉线通知：\n\n({bot_id}) 掉线了，请及时处理。  # 此处会将 bot_id 变量替换为实际 bot_id

```

## TODO

- [ ] 支持 Onebot token 密码验证连接
- [ ] 支持反向 WebSocket 连接