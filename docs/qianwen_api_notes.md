# 千问 (Qianwen) API 逆向工程记录

## 日期
2026-05-24

## API 端点

```
POST https://chat2.qianwen.com/api/v2/chat
```

Query参数（固定模板）：
```
?biz_id=ai_qwen&fe_version=1.0.0&chat_client=h5&device=pc&fr=pc&pr=qwen
&ut={device_id}&la=zh-CN&tz=Pacific%2FAuckland&wv=2.9.3&ve=2.9.3
&nonce={random_11chars}&timestamp={unix_ms}
```

## 签名机制

阿里安全SDK（百夏/baxia），需要4步签名：

```javascript
// 1. 获取签名头 + 重写URL
const { signedHeader, signedUrl } = await window.__QIANWEN_CHAT_SDK__.qwenSign(baseUrl);

// 2. ET签名（防重放）
const bxEt = window.etSign(signedUrl);

// 3. UA指纹
const bxUa = window.__baxia__.postFYModule.getFYToken();

// 4. UMID设备标识
const bxUmid = window.__baxia__.postFYModule.getUidToken();
```

### signedHeader 返回的头：
| Header | 说明 |
|--------|------|
| `clt-acs-sign` | 请求签名（HMAC） |
| `clt-acs-reqt` | 请求时间戳 |
| `clt-acs-request-params` | 参与签名的query参数列表 |
| `eo-clt-dvidn` | 设备标识（加密） |
| `eo-clt-sacsft` | 安全令牌 |
| `eo-clt-snver` | 签名版本 ("lv") |
| `eo-clt-actkn` | 访问令牌 |
| `eo-clt-acs-ve` | ACS版本 ("1.0.0") |
| `clt-acs-caer` | 固定值 "vrad" |
| `eo-clt-acs-kp` | 空字符串 |

### 额外需要手动添加的头：
| Header | 来源 |
|--------|------|
| `bx_et` | `etSign(signedUrl)` |
| `bx-ua` | `postFYModule.getFYToken()` |
| `bx-umidtoken` | `postFYModule.getUidToken()` |
| `x-platform` | 固定 "pc_tongyi" |
| `x-device-id` | UUID格式设备ID |
| `x-chat-id` | 请求ID |
| `x-chat-biz` | JSON: `{chatId, agentId, enableWebp}` |

## 请求体格式

```json
{
  "req_id": "hex32",
  "parent_req_id": "",
  "messages": [{
    "mime_type": "text/plain",
    "content": "用户消息",
    "meta_data": {"ori_query": "用户消息"},
    "status": "complete"
  }],
  "scene": "chat",
  "sub_scene": "",
  "scene_param": "new_chat | continue_chat",
  "session_id": "hex32",
  "biz_id": "ai_qwen",
  "topic_id": "" ,
  "model": "Qwen",
  "from": "default",
  "protocol_version": "v2",
  "messages_merge": false,
  "chat_client": "h5",
  "deep_search": "0",
  "temporary": true
}
```

### model 字段已知值
从 `GET https://chat2-api.qianwen.com/api/v1/model/list` 获取的完整列表：

| modelCode | 显示名 | 说明 | UI可见 |
|-----------|--------|------|--------|
| `Qwen` | Qwen3.6-千问 | 综合AI助手（默认） | ✅ |
| `Qwen3.7-Max` | Qwen3.7-Max | 千问最新旗舰，擅长代码 (NEW) | ✅ |
| `Qwen3.5-Plus` | Qwen3.5-Plus | 最新大语言模型 | 隐藏 |
| `Qwen3.5-Flash` | Qwen3.5-Flash | 简单任务，速度快 | ✅ |
| `Qwen3-Max` | Qwen3-Max | 日常通用型 | ✅ |
| `Qwen3-Max-Thinking-Preview` | Qwen3-Max-Thinking | 多步骤推理 | ✅ |
| `Qwen3-Coder` | Qwen3-Coder | 代码生成 | ✅ |
| `Qwen3-Flash` | Qwen3-Flash | 简单任务，速度快 | 隐藏 |
| `Qwen3-Plus` | Qwen3-Plus | 全能语言模型 | 隐藏 |
| `Qwen3-VL-Plus` | Qwen3-VL-Plus | 视觉理解 | 隐藏 |
| `Qwen3-Coder-Flash` | Qwen3-Coder-Flash | 闪电代码生成 | 隐藏 |
| `Qwen3-VL-235B-A22B` | Qwen3-VL-235B-A22B | 多模态 | 隐藏 |
| `Qwen3-VL-32B` | Qwen3-VL-32B | 视觉语言模型 | 隐藏 |
| `Qwen3-VL-30B-A3B` | Qwen3-VL-30B-A3B | MoE视觉 | 隐藏 |
| `Qwen3-235B-A22B-2507` | Qwen3-235B-A22B-2507 | 最强MoE | 隐藏 |
| `Qwen3-Omni-Flash` | Qwen3-Omni-Flash | 全模态 | 隐藏 |
| `Qwen3-Next-80B-A3B` | Qwen3-Next-80B-A3B | 下一代MoE | 隐藏 |
| `Qwen3-30B-A3B-2507` | Qwen3-30B-A3B-2507 | MoE模型 | 隐藏 |

注意：隐藏模型（show=false）也可以通过API直接调用。

### deep_search 字段
- `"0"` — 普通对话
- `"1"` — 深度搜索模式

## 响应格式（SSE text/event-stream）

### 事件类型（通过 mime_type 区分）

| mime_type | 说明 |
|-----------|------|
| `signal/post` | 意图分析结果（intent） |
| `bar/progress` | 进度标记：`type:"cot"` 开始思考，`type:"generated"` 完成 |
| `bar/iframe` | 搜索来源（sources数组） |
| `multi_load/iframe` | **主要内容**，content字段为累积式全文 |

### 流式内容特点
- **累积式**：每个 `multi_load/iframe` chunk 的 content 包含从头到当前的完整文本
- 需要客户端自行计算 delta（当前content - 上一次content）
- `status: "processing"` 表示生成中，`status: "complete"` 表示该消息完成

### 最终事件
```
event:complete
data:{"error_msg":"","data":{...},"error_code":0,...}
```

### Token用量（在最终chunk的 extra_info.chat_odps.total_usage 中）
```json
{
  "completion_tokens": 605,
  "prompt_tokens": 872,
  "total_tokens": 1477
}
```

### 实际模型信息（extra_info.chat_odps.model_info）
```json
{
  "model": "qwenapp-397b-2026-04-27",
  "audit_result": 1,
  "session_result": 1
}
```

## 已确认的后端模型
- `qwen3.6-plus-2026-05-07` — 短回答/FAQ场景 (model="Qwen")
- `qwenapp-397b-2026-04-27` — 长回答/创作场景 (model="Qwen", 397B参数)
- Qwen3.7-Max — 旗舰模型，擅长代码（model="Qwen3.7-Max"）

## SSE格式差异
- **Qwen (默认)**: 纯 `data:` 行
- **Qwen3.7-Max**: 使用 `event:message\ndata:` 格式（标准SSE）
- 两种格式的 data JSON 结构相同

## 免登录使用
- 设置 `temporary: true` 即可无需登录
- 有使用限制（具体限额未测试）
- 登录后可获得更多配额和历史记录

## 实现方案

采用与豆包相同的 Playwright in-browser fetch 方案：
1. Playwright 打开 qianwen.com 页面
2. 等待安全SDK加载（`__QIANWEN_CHAT_SDK__`, `etSign`, `__baxia__`）
3. 通过 `page.evaluate()` 在浏览器内执行签名+fetch
4. 通过 `expose_function` 桥接SSE chunks回Python
5. Python侧将累积content转换为OpenAI delta格式

## 文件
- `doubao2api/qianwen_client.py` — 浏览器客户端实现
- `doubao2api/unified_server.py` — 已集成路由（model: qianwen/qianwen-search）

## 部署配置
```bash
QIANWEN_ENABLED=true
QIANWEN_HEADLESS=true
QIANWEN_BROWSER_DATA=/root/.qianwen_browser
```

## 待探索
- [x] 切换到 Qwen3.7-Max 模型 — 只需设置 `model: "Qwen3.7-Max"`
- [ ] 登录态下的额外功能
- [ ] 多轮对话（topic_id复用）
- [ ] 深度搜索模式的响应格式差异
- [ ] 速率限制和配额
- [ ] 图片/文件上传
- [ ] Thinking模型（Qwen3-Max-Thinking-Preview）的思考过程格式
- [ ] 隐藏模型（Qwen3-VL系列、Qwen3-Omni-Flash等）的可用性测试
