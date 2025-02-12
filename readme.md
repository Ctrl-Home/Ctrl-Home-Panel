## 被控端JSON写法
````json
{
  "ip_address": "你的节点服务器的IP地址",
  "port": "你的节点服务器监听的端口号",
  "role": "节点的角色，可以是 'ingress' (入口), 'egress' (出口), 或 'both' (两者都是)",
  "protocols": "节点支持的协议列表，用逗号分隔，例如 'vless,trojan,shadowsocks'",
  "secret_key": "用于节点身份验证的密钥，你需要自己生成一个安全的密钥"
}