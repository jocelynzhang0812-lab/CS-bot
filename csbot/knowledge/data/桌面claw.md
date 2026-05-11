# Kimi Claw Desktop 知识库

&gt; 适用于：通过 Kimi 桌面客户端一键部署到本地电脑的 Kimi Claw 用户，同时支持macOS和Windows

---

## 一、基础认知

### Q1: 什么是 Kimi Claw Desktop？

Kimi 桌面客户端内一键部署的本地 OpenClaw，运行在用户本机上的 AI 助手系统。与云端部署不同，所有数据（工作文件、记忆、人设）均存储在本地用户文件夹中。

**前置条件：**
- 下载 Kimi 桌面客户端
- 登录账号并升级至 Allegretto 会员等级以上
- 每个账号暂仅支持最多 1 个 Kimi Claw Desktop

---

### Q2: 如何创建 Kimi Claw Desktop？

**STEP 1：** 下载 Kimi 桌面客户端，登录账号，确认 Allegretto 会员等级

**STEP 2：** 前往 Kimi Claw 页面，点击【部署"在我的电脑上"】
- 若账号下已有其他电脑的 Kimi Claw Desktop，需确认是否断开旧连接
- 若本机已安装其他版本本地 OpenClaw，可选择复刻人设、记忆、聊天记录、工作区文件

**STEP 3：** 根据喜好修改 Kimi Claw Desktop 的昵称

---

### Q3: Kimi Claw Desktop 的文件存储在哪里？

部署后会在本地用户文件夹创建 `.kimi_openclaw` 隐藏文件夹，存放：
- 对话记录
- Claw 人设
- 记忆文件
- Skill 能力文件
- 所有工作区文件

---

### Q4: 如何删除 Kimi Claw Desktop？

**macOS：**
1. 开启访达（Finder）
2. 找到用户文件夹（小房子图标）
3. 显示隐藏文件夹：按 `Command + Shift + .`
4. 找到并删除 `.kimi_openclaw` 文件夹
5. 如需保留内容，可先复制文件夹到别处，后续新 Claw 可读取迁移

**Windows：** 已上线

---

## 二、使用技巧

### Q5: 如何修改 Kimi Claw Desktop 的人设？

与云端相同，通过自然语言设定：
- **名字与身份：** 给新名字、职业或角色定位
- **说话方式：** 调整语气风格（简短、正式、幽默等）
- **固定开场/结尾：** 每次回复前加固定语句或结尾总结行动项

---

### Q6: 如何安装和使用 Skill？

**入口：** 在对话中让 Kimi Claw 去 Clawhub 技能库搜索并安装

**适合场景：**
- 信息整理：新闻汇总、竞品对比、会议纪要模板化
- 分析任务：股票/行业梳理、数据解读、风险点提取
- 工作流：从需求→拆解→输出→复盘的一整套流程

**⚠️ 安全建议：** 公开 Skill 不一定安全，可以自己用 Coding 软件写 Skill 后一键导入。

---

### Q7: 如何设定定时任务？

**强烈建议：** 非必要不设置整点任务，避免拥堵。建议设置 08:13、12:47 等非整点时间。

**万能句式：**在【时间】执行【任务】，输出【格式】，并遵守【约束】。

---

## 三、命令行与功能

> **口径说明：** Kimi Claw Desktop 不提供独立 Terminal / SSH，仅支持对话命令。

### Q8: Kimi Claw Desktop 支持哪些命令？

可直接在 Claw 对话框输入以下命令：

#### 基础系统

| 命令 | 功能 |
|------|------|
| `/help` | 查看所有可用命令 |
| `/status` | 系统运行状态与连接健康度 |
| `/ping` | 测试网关响应 |
| `/cron` | 查看/管理定时任务 |
| `/cron add "<schedule>" <command>` | 添加定时任务，如 `/cron add "0 9 * * *" /news` |
| `/cron rm <id>` | 删除指定 ID 的定时任务 |
| `/config` | 查看当前用户配置 |
| `/config set <key> <value>` | 修改配置项 |
| `/file` 或 `/upload` | 查看/管理已上传文件列表 |
| `/search <query>` | 触发联网搜索 |
| `/new` | 开启新 Session（保留历史） |
| `/reset` | 重置当前 Session（清空上下文） |
| `/compact [instructions]` | 压缩历史对话，保留关键信息 |
| `/stop` | 终止当前正在进行的任务 |

#### 技能管理

| 命令 | 功能 |
|------|------|
| `/skills` | 列出已安装的所有 Skill |
| `/skills info <skill_id>` | 查看指定 Skill 详情 |
| `/skills install <url或id>` | 安装新 Skill |
| `/skills uninstall <skill_id>` | 卸载指定 Skill |
| `/skills update <skill_id>` | 更新 Skill 至最新版本 |
| `/skills reload` | 重载所有 Skill |

#### 定时任务

| 命令 | 功能 |
|------|------|
| `/cron` | 查看当前所有定时任务列表 |
| `/cron log <task_id>` | 查看指定任务的执行日志与报错 |
| `/cron enable/disable <task_id>` | 启用或暂停定时任务 |

#### 记忆空间

| 命令 | 功能 |
|------|------|
| `/memory` | 查看当前记忆条目数量与容量 |
| `/memory search <关键词>` | 搜索记忆内容 |
| `/memory export` | 导出记忆文件（备份用） |

#### 配置与调试

| 命令 | 功能 |
|------|------|
| `/config` | 查看当前网关与平台配置 |
| `/config reload` | 重载配置文件 |
| `/logs` | 查看最近系统日志 |
| `/debug on/off` | 开启或关闭调试模式 |

**快速诊断流程：** Skill 或定时任务异常时，依次执行 `/status` → `/logs` → `/cron log <任务ID>` 定位问题。

---

### Q9: Kimi Claw Desktop 支持命令行终端控制吗？

**暂不支持。** 与云端部署不同，桌面端无法通过【设置】→【打开终端】执行 Shell 操作。所有控制通过对话框命令完成。

---

## 四、升级与版本管理

### Q10: Kimi Claw Desktop 如何升级？

暂不支持手动升级，将跟随 Kimi 桌面客户端的升级而同步升级。

---

### Q11: 可以手动升级飞书插件吗？

**不建议。** 飞书插件升级会同时升级 OpenClaw 版本，导致与当前环境不兼容。新安装的 Kimi Claw Desktop 已内置适配的最新版本插件。


### Q12: 飞书连接问题如何诊断？

向 Kimi Claw 发送：
- `/feishu start` — 确认安装状态
- `/feishu doctor` — 检查配置是否正常
- `/feishu auth` — 批量完成用户授权


### Q14: Kimi Claw Desktop 可以收发文件吗？

可以。
发送文件： 通过对话直接发送图片、文件，Kimi Claw Desktop 会使用工具查看
接收文件： 最新版本已支持向你发送文件，如无法发送请升级桌面客户端到最新版本

### Q15: 前一天聊过的内容为什么重新打开后没有了？

OpenClaw 默认每天凌晨 4 点自动重置对话，目的是清理过长上下文，确保稳定响应。
如需调整重置频率或时间，可修改系统的 `config.yaml` 配置文件。
保留重要信息的方法：对话中明确说“请记住我的偏好”或“记住 XXX 到 Memory 里”，系统会将内容更新到长期记忆文件（`MEMORY.md`）。

通用排查与更多场景说明请参考《常见bug》中的记忆与上下文章节。

### Q16: Kimi Claw Desktop 失忆了怎么办？

OpenClaw 每天凌晨 4 点更新会话，清空上下文，未记录到 MEMORY 的内容可能丢失
和 AI 对话时说"记住 XXX 到 Memory 里"，让模型更积极地将内容记录到 MEMORY.md 和相关记忆文件

### Q17: 会员到期后记忆能留存多久？
记忆文件存储在本地。会员到期未续费时，Kimi Claw Desktop 无法继续使用，但记忆文件仍保留在本地 .kimi_openclaw 文件夹中。续费后即可继续使用。

### Q18: Kimi Claw Desktop 可以删除吗？

目前 Desktop 版的 Claw 暂不支持删除操作，该功能后续会开发上线。如需临时停用，可退出桌面客户端或取消自动启动。

### Q19: 桌面版的 Kimi Claw 完全没反应了，重启也没用怎么办？

**第一步：测试基础响应**
尝试发送一个较长的输入，看看是否会回复，例如：
> 今日天气如何

**第二步：如果仍无响应，请提供日志文件**

- **macOS**：
  - 日志路径：`/Users/你的用户名/Library（资源库）/Logs/kimi-desktop/main.log`
  - 如果看不见 `Library（资源库）` 文件夹，在 Finder 中使用快捷键 `Command + Shift + .` 即可显示隐藏文件夹

- **Windows**：
  - 日志路径：`C:\Users\用户名\AppData\Roaming\kimi-desktop\logs\main.log`








