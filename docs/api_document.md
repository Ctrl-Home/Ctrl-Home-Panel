# JustRelay Panel API 文档

**基础信息**
- 当前版本: v1.2.0
- 基础URL: `http://localhost:5000`
- 认证方式: JWT (通过Cookie传递)

## 认证模块
### 用户登录
```http
POST /api/v1/auth/login
```
**请求体**
```json
{
  "username": "admin",
  "password": "securepassword"
}
```

**成功响应**
```json
{
  "code": 200,
  "message": "登录成功",
  "data": {
    "user_id": 1,
    "role": "admin"
  }
}
```
**Cookie设置**
- access_token_cookie
- refresh_token_cookie

### 令牌刷新
```http
POST /api/v1/auth/refresh
```
**要求**：携带有效的refresh_token cookie

**成功响应**
```json
{
  "code": 200,
  "message": "令牌已刷新"
}
```

### 用户登出
```http
POST /api/v1/auth/logout
```
**效果**：清除JWT cookies

## 用户管理模块
### 注册用户
```http
POST /api/v1/users/register
```
**参数**
| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| username | string | 是 | 4-20位字符 |
| password | string | 是 | 最小8位 |
| confirm_password | string | 是 | 必须与password一致 |

**冲突响应**
```json
{
  "code": 409,
  "message": "用户名已存在"
}
```

### 获取用户信息
```http
GET /api/v1/users/{user_id}
```
**权限要求**：JWT认证且user_id匹配

**响应字段**
```json
{
  "user_id": 1,
  "username": "admin",
  "role": "admin"
}
```

## 引擎控制模块
### 设备状态查询
```http
GET /api/engine/status/sensors
GET /api/engine/status/sensors/{sensors_id}
GET /api/engine/status/actuators
GET /api/engine/status/actuators/{actuators_id}
GET /api/engine/status/device
GET /api/engine/status/device/{device_id}
```

**设备状态示例**
```json
{
  "device_id": "sensor-01",
  "type": "temperature",
  "value": 25.5,
  "timestamp": "2025-04-09T12:00:00Z"
}
```

### 规则管理
| 方法 | 路径 | 功能 |
|------|------|------|
| GET | /api/engine/rules | 获取全部规则 |
| POST | /api/engine/rules | 创建新规则 |
| PUT | /api/engine/rules/{rule_id} | 更新规则 |
| DELETE | /api/engine/rules/{rule_id} | 删除规则 |

**规则数据结构**
```json
{
  "id": "rule-001",
  "name": "温度告警",
  "condition": "value > 30",
  "action": "activate_cooling",
  "enabled": true
}
```

## 节点管理模块
### 注册/更新节点
```http
POST /node/create
```
**表单参数**
- ip_address: 节点IP
- port: 端口号(1-65535)
- role: [ingress, egress, both]
- protocols: 逗号分隔协议列表

**成功响应**
```http
HTTP/2 302 Found 
Location: /node/dashboard
Flash: 节点已注册
```

### 节点配置获取
```http
GET /node/config/{node_id}
```
**Header要求**
```
X-Secret-Key: <节点密钥>
```

**响应包含**
- 节点基础信息
- 应用规则列表
- 最近心跳时间

### 节点心跳
```http
POST /node/heartbeat/{node_id}
```
**维护节点在线状态**
