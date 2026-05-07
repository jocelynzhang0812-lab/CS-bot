# kb_02 — 常见bug

## 1. 实例离线与崩溃修复

### 1.1 实例离线 / 无法重启的场景对照

| 场景 | 用户看到的报错 | 底层报错信息 |
|------|---------------|-------------|
| 完全离线 | "Bot 离线" 或 "连接超时" | `failed to execute script via SSH and cloud assistant` |
| 无法重启 | "重启失败" | `Instance unreachable` |
| 无法升级 | "升级失败" | `Instance unreachable` |

### 1.2 Kimi Claw 一直连不上 / 崩溃怎么办？

**场景一：提示"与云端电脑的连接已断开"**

原因：连接稳定性问题。

解决方法：更新 Kimi Claw 插件和软件版本：

- 进入 Kimi Claw 页面 → 设置 → 更新插件到最新版本（Web 端升级即可）
- Android：升级到 >= v2.6.3
- iOS：升级到 >= v2.6.1（审核中，预计很快发布）

**场景二：提示"与 Kimi 连接已断开，请尝试重启服务或自动修复"**

原因：AI 在修改配置过程中误改了 OpenClaw 配置。

当前解决方案：删除 Bot，重新创建新 Bot（后续版本将提供保留 Workspace 内容的修复功能）。

**自助修复步骤（点击 ⚙ 设置按钮）：**

1. 先尝试【修复 Kimi Claw 配置】：重启实例，缓解磁盘满等导致的卡死问题
2. 若未解决 → 尝试【恢复初始设置】（不会丢失工作空间文件和记忆，但需重新配置聊天机器人配对）
3. 若仍未解决 → 加入飞书交流群，并发送你的 **Kimi Claw ID**（位于 Kimi Claw 头像下方）

> **获取 Bot ID 方法：** 前往 https://www.kimi.com/bot → 点击右上角【设置】→ 复制个人昵称下方的字符串。

### 1.3. Bot 显示红色离线

**解决步骤**：
1. 设置 → 重启 Kimi Claw
2. 设置 → 修复配置
3. 设置 → 恢复初始设置（保留记忆和定时任务）


## 2. 连接与稳定性故障

### 2.1 Kimi Claw Desktop 不回消息或回复很慢怎么办？

**常见场景与报错对照：**

| 场景 | 用户看到的报错 | 底层报错类型 |
|------|---------------|-------------|
| Bridge 完全断开 | "Bot 未连接" 或 "连接失败" | `bridge ACP disconnected` |
| Bridge 重连中 | 消息发送失败，提示重试 | `bridge state reconnecting -> connecting` |
| 资源耗尽 | "服务繁忙，请稍后再试" | `code=resource_exhausted message=connect stream failed` |
| 订阅失败 | 无法接收消息 | `subscribe failed reason=stream_error` |

**排查步骤：**

1. 对话框一直显示加载状态 → 再发一条消息，或刷新页面
2. 依然无反馈 → 设置内重启 Gateway 服务，重启后重新对话
3. 仍不可行 → 设置内点击【修复 Kimi Claw 配置】
4. 以上均失败 → 点击【恢复初始配置】

### 2.2 显示 "Gateway: closed (1000)"

**原因**：Gateway 连接中断

**解决**：
1. 设置 → 重启 Kimi Claw
2. 设置 → 修复配置
3. 设置 → 恢复初始设置

## 3. 超时问题

### 3.1 IM runtime dispatch out after 300000ms 超时怎么办？

**常见场景与报错：**

| 场景 | 用户看到的报错 | 报错信息 |
|------|---------------|----------|
| IM dispatch 超时 | 消息一直"发送中"无响应 | `IM runtime dispatch timed out after 300000ms` |
| SendMessageStream 超时 | 消息发送失败 | `IM SendMessageStream completion timed out after 5000ms` |
| 消息过期 | 消息未送达 | `message om_xxx expired, discarding` |

**解决方法：**

1. **拆分长任务：** 将大任务拆分为多个小任务，每个在 10 分钟内完成
2. **使用后台任务：** 对需要长时间运行的任务，使用 background 模式：

```bash
exec command="your-long-task" background=true
```

3. **优化任务：**
   - 减少单次处理的数据量
   - 使用更高效的算法
   - 避免不必要的重试

4. **调整超时设置（不推荐）：** 可在配置中增加超时时间，但可能影响稳定性

## 4. 记忆丢失与上下文保存

### 4.1 前一天聊过的内容，重新打开后为什么没有了？

**原因：** OpenClaw 默认每天凌晨 4 点自动重置对话，定期清理过长的上下文，防止 AI 因信息过载产生幻觉。

**调整方式：** 修改系统的 `config.yaml` 配置文件，可调整重置频率或时间。

**保留重要信息的最佳实践：**

- 在对话中明确告知 AI 需要记住的内容，例如：`"请记住我的偏好"`
- 使用明确指令引导系统将内容更新到长期记忆

### 4.2 Kimi Claw Desktop 失忆了怎么办？

- OpenClaw 每天凌晨 4 点清空上下文，未记录到 MEMORY 的内容会丢失
- 在对话时说：`"记住 XXX 到 Memory 里"`，让模型主动将内容记录到 MEMORY.md 及相关记忆文件

### 4.3 不续费后记忆能留存多久？

Kimi Claw Desktop 的记忆文件**存储在本地**，与云端版本不同：

| 状态 | 说明 |
|------|------|
| 记忆文件位置 | 本地 `.kimi_openclaw` 文件夹，始终保留 |
| 会员到期后 | Kimi Claw Desktop 无法继续使用，但本地记忆文件仍保留 |
| 续费后 | 即可继续使用，记忆文件完整恢复 |

会员权益、额度与续费口径请以《会员权益》为准。

---

## 5. 对话限制与 API Rate Limit

### 5.1 对话 token 超过最大限制怎么办？

1. 向模型发送 `/new` 新建对话
2. 若 `/new` 后仍超出 context，可能是模型误加载了过多 Skill，加入用户交流群反馈

### 5.2 提示 "API rate limit reached" 怎么办？

**常见场景：**

| 场景 | 用户看到的报错 | 报错信息 |
|------|---------------|----------|
| 触发限流 | "服务繁忙，请稍后再试" 或固定回复 | `⚠️ API rate limit reached. Please try again later.` |
| 重试后仍失败 | 重复相同内容或错误提示 | `embedded run agent end: isError=true error=⚠️ API rate limit reached` |
| failover 后 | "当前服务不可用" | `decision=surface_error reason=rate_limit` |

**解决**：
1. 检查会员额度：https://www.kimi.com/code/console?from=membership
2. 尝试「设置 → 一键修复 Kimi Claw」
3. 如额度充足仍报错，联系客服

---

### 6. 定时任务不执行

**检查命令**：
```
/cron          # 查看任务列表
/status        # 查看系统状态
/cron log <ID> # 查看任务日志
```

### 7. 不回消息或响应慢

**排查步骤**：
1. 再发一条消息测试
2. 刷新页面
3. 设置 → 重启 Gateway
4. 设置 → 修复配置
5. 设置 → 恢复初始设置

详细排查：https://www.kimi.com/help/kimi-claw/slow-no-response
