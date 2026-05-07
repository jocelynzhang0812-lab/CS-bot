# Kimi Code 帮助文档


---

# Kimi Code 权益说明

Kimi Code 是 Kimi 会员权益中的一项服务，为会员提供编程相关的支持和功能，帮助会员在个人开发的过程中更高效地完成编程任务。

## 计费方式

- Kimi Code 的使用**包含在套餐费用中**，无需额外付费。
- 每次调用会消耗套餐内的统一额度，不同套餐包含的额度不同。
- 系统优先消耗获赠额度，再消耗套餐额度。

## 额度刷新

额度按 **7 天** 为一个周期进行刷新：

- 以订阅日 D1 为起点，每 7 天刷新一次。
- 刷新周期为：D1–D7、D8–D14、D15–D21、D22–D28。
- 未用完的额度**不会**累计到下一个周期。

## 使用范围

Kimi Code 权益适用于以下工具：

| 工具 | 说明 |
| --- | --- |
| **Kimi Code CLI** | Kimi 官方命令行 AI Agent |
| **Claude Code** | Anthropic 的命令行编程助手 |
| **Roo Code** | VS Code 中的 AI 编程插件 |

在其他未列出的平台或工具中使用 Kimi Code 的 API Key，可能会被视为滥用行为，并可能导致权益受限。请在上述支持的工具中使用，以获得最佳体验和保障。


---

# 定制化与参考

Kimi Code CLI 提供了丰富的定制化选项，让你可以根据自己的需求调整 AI 的行为和工作方式。

## 配置文件

Kimi Code CLI 使用 `~/.kimi/config.toml` 作为全局配置文件，支持 TOML 和 JSON 两种格式。你可以在配置文件中设置：

- **API 供应商和模型**：配置不同的模型提供商、API 地址和密钥。
- **默认模型**：指定默认使用的模型。
- **运行参数**：调整超时、并发、输出格式等运行时参数。

## AGENTS.md 项目配置

在项目根目录放置 `AGENTS.md` 文件，可以为 AI 提供项目级别的上下文信息：

- **项目背景**：描述项目的功能、架构和技术栈。
- **构建步骤**：如何安装依赖、构建项目、运行测试。
- **代码规范**：命名规范、目录结构约定、代码风格偏好。
- **注意事项**：需要特别注意的安全限制、性能要求等。

使用 `/init` 命令可以让 AI 自动扫描项目并生成初始的 `AGENTS.md`。你也可以手动编辑该文件，添加更多项目特定的信息。`AGENTS.md` 可以放在项目的任意子目录中，AI 会自动加载相关的配置。

## 自定义 System Prompt

你可以通过以下方式自定义 AI 的 system prompt：

- **全局 system prompt**：在 `~/.kimi/AGENTS.md` 中编写，对所有项目生效。
- **项目级 system prompt**：在项目根目录的 `AGENTS.md` 中编写，仅对当前项目生效。
- **启动参数**：使用 `--system-prompt` 参数在启动时指定。

项目级配置会覆盖全局配置，启动参数优先级最高。

## MCP 集成

Kimi Code CLI 支持 Model Context Protocol（MCP），可以连接外部工具和数据源，扩展 AI 的能力：

- **MCP 服务器配置**：在配置文件中添加 MCP 服务器地址，AI 即可调用外部工具。
- **内置 MCP 支持**：部分常用的 MCP 工具已内置，无需额外配置。
- **自定义 MCP 服务器**：你可以开发自己的 MCP 服务器，为 AI 提供特定领域的能力。

MCP 配置可以写在 `~/.kimi/config.toml` 或项目级别的配置文件中。

## 环境变量

Kimi Code CLI 支持通过环境变量进行配置，适合在 CI/CD 或脚本中使用：

| 环境变量 | 说明 |
| --- | --- |
| `KIMI_API_KEY` | API 密钥 |
| `KIMI_BASE_URL` | 自定义 API 地址 |
| `KIMI_MODEL` | 默认模型名称 |
| `KIMI_MAX_TOKENS` | 最大输出 token 数 |

环境变量的优先级高于配置文件中的设置。

## 更多参考

- **斜杠命令参考**：使用 `/help` 查看所有可用命令。
- **CLI 参数参考**：运行 `kimi --help` 查看所有启动参数。
- **官方文档**：访问 [Kimi Code 文档](https://kimi.com/code/docs) 获取最新的完整文档。


---

# 开始使用 Kimi Code CLI

Kimi Code CLI 是一个运行在终端中的 AI Agent，帮助你完成软件开发任务和终端操作。它可以阅读和编辑代码、执行 Shell 命令、搜索和抓取网页，并在执行过程中自主规划和调整方案。

## 适合场景

- **编写和修改代码**：描述需求，AI 自动完成代码编写与修改。
- **理解项目**：快速了解项目架构、代码逻辑和文件作用。
- **自动化任务**：批量修改代码、添加文档、生成测试用例等重复性工作。

## 三种使用方式

| 方式 | 命令 | 说明 |
| --- | --- | --- |
| 交互式终端 | `kimi` | 在终端中与 AI 对话，适合日常开发 |
| 浏览器界面 | `kimi web` | 在浏览器中打开交互界面 |
| Agent 集成 | `kimi acp` | 通过 ACP 协议集成到 IDE 中使用 |

## 安装

在终端中运行以下命令安装 Kimi Code CLI：

安装完成后，验证安装是否成功：

## 首次运行

1. 进入你的项目目录：

2. 启动 Kimi Code CLI：

3. 执行 `/login` 命令完成登录授权：

   系统会提示你选择登录平台，按提示完成授权即可。

4. 配置完成后，你就可以开始与 AI 对话了。

## 生成 AGENTS.md

在项目目录下执行 `/init` 命令，Kimi Code CLI 会自动扫描项目结构并生成 `AGENTS.md` 文件：

`AGENTS.md` 用于向 AI 提供项目的背景信息、构建步骤、代码规范等上下文，帮助 AI 更准确地理解你的项目。


---

# 在 IDE 中使用

Kimi Code CLI 支持通过 Agent Client Protocol（ACP）集成到 IDE 中，让你在编辑器内直接使用 AI 编程能力。

## 在 Zed 中使用

[Zed](https://zed.dev/) 是一个原生支持 ACP 的现代 IDE。

在 Zed 的配置文件 `~/.config/zed/settings.json` 中添加以下配置：

保存配置后，在 Zed 的 Agent 面板中即可选择 Kimi Code 进行对话。

## 在 JetBrains IDE 中使用

JetBrains 全家桶（IntelliJ IDEA、PyCharm、WebStorm 等）通过 AI Assistant 插件支持 ACP。

### 前置条件

1. 确保 AI Assistant 插件已安装并启用。
2. 需要在注册表（Registry）中启用实验性功能：
   - 打开 **Help → Find Action**，搜索 `Registry...`
   - 找到并勾选 `llm.enable.mock.response`

### 配置步骤

1. 打开 **AI 聊天面板**。
2. 点击 **Configure ACP agents**。
3. 添加新的 ACP 配置：

配置完成后，在 AI 聊天面板中选择 Kimi Code 即可开始使用。


---

# 集成到工具

除了 IDE 集成外，Kimi Code CLI 还可以集成到其他工具中，提升你的终端工作流效率。

## Zsh 插件

[zsh-kimi-cli](https://github.com/MoonshotAI/zsh-kimi-cli) 是一个 Zsh 插件，让你可以在 Zsh 中快速切换到 Kimi Code CLI。

### Oh My Zsh 安装

如果你使用 Oh My Zsh，可以按以下步骤安装：

1. 将仓库克隆到 Oh My Zsh 的自定义插件目录：

   ```bash
   git clone https://github.com/MoonshotAI/zsh-kimi-cli.git \
     ${ZSH_CUSTOM:-~/.oh-my-zsh/custom}/plugins/kimi-cli
   ```

2. 在 `~/.zshrc` 中将 `kimi-cli` 添加到插件列表：

   ```bash
   plugins=(
     # ... 其他插件
     kimi-cli
   )
   ```

3. 重新加载配置：

   ```bash
   source ~/.zshrc
   ```

### 使用方式

安装完成后，在终端中按 **Ctrl-X** 即可快速切换到 Kimi Code CLI，无需手动输入 `kimi` 命令。


---

# 交互与输入

Kimi Code CLI 提供了多种交互方式，帮助你高效地与 AI 协作。

## Agent 模式与 Shell 模式

Kimi Code CLI 有两种输入模式：

- **Agent 模式**（默认）：输入的内容会发送给 AI 处理，AI 会阅读代码、执行命令、修改文件等。
- **Shell 模式**：直接执行 Shell 命令，无需离开 Kimi Code CLI。

使用 **Ctrl-X** 在两种模式之间快速切换。Shell 模式下也支持部分斜杠命令，如 `/help`、`/exit`、`/version` 等。

## Thinking 模式

Thinking 模式让 AI 在回答前进行更深入的思考，适合处理复杂问题。

- 使用 `/model` 命令切换模型和 Thinking 模式。
- 启动时可通过 `--thinking` 参数直接开启 Thinking 模式。

## 多行输入

按 **Ctrl-J** 插入换行，进行多行输入。适合输入较长的 prompt 或粘贴多行代码片段。

## 剪贴板粘贴

按 **Ctrl-V** 从剪贴板粘贴内容，支持粘贴文本和图片。粘贴图片时，AI 可以直接理解图片内容（如截图、设计稿、报错截图等）。

## 斜杠命令

以 `/` 开头的命令用于控制会话、配置和调试。常用命令包括：

| 命令 | 说明 |
| --- | --- |
| `/help` | 显示帮助信息 |
| `/login` | 登录授权 |
| `/model` | 切换模型和 Thinking 模式 |
| `/sessions` | 列出和切换会话 |
| `/clear` | 清空当前上下文 |
| `/compact` | 压缩上下文 |
| `/init` | 生成 AGENTS.md |
| `/exit` | 退出 CLI |

在输入框中输入 `/` 后，会自动显示可用命令列表。

## @ 路径补全

在输入中使用 `@` 符号可以引用文件或目录路径，系统会自动补全：

这样 AI 会自动读取引用的文件内容作为上下文。

## 结构化问答

在某些场景下，AI 会以结构化选项的形式请求你的输入。使用**方向键**选择选项，按 **Enter** 确认。

## 审批确认

当 AI 需要执行文件修改、Shell 命令等操作时，会请求你的确认。你可以选择：

| 选项 | 说明 |
| --- | --- |
| **允许** | 允许本次操作 |
| **本会话允许** | 允许同类操作在当前会话中不再询问 |
| **拒绝** | 拒绝本次操作 |

### YOLO 模式

如果你信任 AI 的操作，可以使用 YOLO 模式跳过所有确认：


---

# 会话与上下文

Kimi Code CLI 支持多会话管理和上下文持久化，让你可以随时中断和恢复工作。

## 会话续接

你可以通过多种方式恢复之前的会话：

- **继续最近会话**：使用 `--continue`（或 `-c`）参数继续上一次对话：

- **指定会话 ID**：使用 `--session` 参数恢复特定会话：

- **列表切换**：在 CLI 中输入 `/sessions`（或 `/resume`）命令，查看会话列表并选择要恢复的会话。

## 启动回放

恢复会话时，Kimi Code CLI 会自动回放历史消息，帮助你快速回忆之前的上下文和进展。

## 状态持久化

以下状态会在会话之间自动保存和恢复：

- **审批决策**：你在会话中做出的「本会话允许」等审批决策会被记住。
- **动态子 Agent**：会话中创建的子 Agent 配置会被保留。
- **额外目录**：通过命令添加的额外工作目录也会被持久化。

这意味着恢复会话后，你可以无缝继续之前的工作。

## 清空与压缩

Kimi Code CLI 会在需要的时候自动对上下文进行压缩，确保对话能够继续。你也可以使用斜杠命令手动管理上下文：

### 清空上下文

输入 `/clear`（或 `/reset`）可以清空当前会话的所有上下文，重新开始对话：

### 压缩上下文

输入 `/compact` 可以压缩上下文，保留关键信息的同时减少 token 占用：

你也可以在压缩时附带说明，告诉 AI 哪些信息需要重点保留：

### 上下文状态

CLI 底部的状态栏会实时显示当前的 context 使用率，帮助你了解上下文的消耗情况。当使用率较高时，建议使用 `/compact` 进行压缩，避免丢失重要信息。


---

# 常见使用案例

以下是 Kimi Code CLI 在日常开发中的几个典型使用场景，每个场景附带了示例 prompt 供参考。

## 实现新功能

直接用自然语言描述你的需求，AI 会自动阅读相关代码、编写新代码并进行验证。

## 修复 Bug

将错误信息直接粘贴给 AI，它会自动定位问题根源并提供修复方案。

## 理解项目

当你接手一个新项目或需要了解某段代码的逻辑时，直接询问即可。

## 自动化小任务

适合批量修改代码、添加文档、生成测试等重复性工作。

## 通用任务

Kimi Code CLI 不仅限于编程，还可以处理调研、数据分析、批量文件操作等任务。


---

# Kimi Code 会员权益指南

Kimi Code 是 Kimi 会员计划中专为代码开发打造的权益，为开发者提供高性能的 AI 编程能力。你可以通过 Kimi Code CLI、Claude Code、Roo Code 等多种工具使用该权益。

## 核心优势

- **广泛兼容**：支持 Kimi Code CLI、Claude Code、Roo Code 等主流 Coding Agent，灵活接入你习惯的开发工具。
- **极速响应**：最高可达 100 Tokens/s 的生成速度，显著提升编码效率。
- **高频并发**：每 5 小时约 300–1200 次请求（视套餐而定），最高支持 30 路并发，满足高强度开发场景。

## 快速开始

根据你的情况选择对应的方式：

- **新用户**：前往 [kimi.com/code](https://kimi.com/code) 登录，选择 Coding Plan 套餐完成订阅。
- **已订阅用户**：进入控制台管理你的 API Key，即可开始使用。

## 获取 API Key

1. 登录 [Kimi 控制台](https://kimi.com/code)。
2. 进入 **API Keys** 页面。
3. 点击 **创建新的 API Key**。
4. 复制并妥善保存你的 API Key（创建后仅显示一次）。

## 一键登录

在 Kimi Code CLI 中，你可以使用 `/login` 命令快速完成授权，无需手动复制 API Key：

系统会自动完成设备授权与账号绑定，整个过程只需几秒。

## 设备管理

- 每个账号可在多台设备上使用。
- **30 天未活跃**的设备授权会自动失效，届时需要重新执行 `/login` 完成授权。
- 你可以在控制台查看和管理已授权的设备。


---

# 在第三方 Coding Agent 中使用

Kimi Code 权益支持在 Claude Code 和 Roo Code 中使用，让你可以在自己习惯的编程工具中享受 Kimi 的 AI 能力。

## 前提条件

- 已订阅 Kimi 会员并开通 Kimi Code 权益。
- 已获取 API Key（在 [Kimi 控制台](https://kimi.com/code) 中创建）。

## 在 Claude Code 中使用

[Claude Code](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview) 是 Anthropic 推出的命令行编程助手。

### 配置步骤

1. 设置环境变量：

   ```bash
   export ANTHROPIC_BASE_URL=https://api.kimi.com/coding/v1
   export ANTHROPIC_API_KEY=你的API Key
   ```

2. 启动 Claude Code，使用 `kimi-k2.5` 模型：

   ```bash
   claude --model kimi-k2.5
   ```

## 在 Roo Code 中使用

[Roo Code](https://github.com/RooCodeInc/Roo-Code) 是一款 VS Code 中的 AI 编程插件。

### 安装 Roo Code

1. 在 VS Code 扩展市场搜索 **Roo Code** 并安装。
2. 安装完成后，活动栏会出现 Roo Code 图标；如未出现，可重启 VS Code。

### 配置 Kimi Code 模型

1. 打开 Roo Code 面板，进入**设置页**。
2. 在 **Providers** 区域选择 **OpenAI Compatible**，按照提示填写：

   | 配置项 | 值 |
   | --- | --- |
   | Entrypoint | `https://api.kimi.com/coding/v1` |
   | API Key | 你的 API Key |
   | Model | `kimi-k2.5` |

3. 保存配置后即可开始使用。

## 注意事项

- Kimi Code 权益仅支持在 **Kimi Code CLI**、**Claude Code** 和 **Roo Code** 中使用。
- 在其他未授权的平台或工具中使用 API Key 可能被视为违规行为，并可能导致权益受限。
- 如有疑问，请参阅 [权益说明](benefits.md) 或联系 Kimi 客服。


---

# Kimi Code for VS Code 快速开始

Kimi Code for VS Code 是集成于 Visual Studio Code 的扩展插件。安装后，你可以在编辑器内直接发起提问、审查代码 diff 并快速提交变更。插件能够读取你引用的文件内容，理解项目上下文，提供更精准的编程辅助。

## 安装

1. 打开 VS Code。
2. 进入扩展市场（快捷键 `Ctrl+Shift+X` / `Cmd+Shift+X`）。
3. 搜索 **Kimi Code**。
4. 点击 **安装**。

## 登录配置

安装完成后，需要登录你的 Kimi 账号：

1. 打开 Kimi Code 聊天面板。
2. 输入 `/login` 命令。
3. 按提示完成授权，系统会自动绑定你的账号。

## 基本使用

### 聊天面板

Kimi Code 在 VS Code 侧边栏提供了原生的聊天面板，你可以：

- **提问和对话**：直接输入问题，AI 会结合项目上下文进行回答。
- **引用文件**：使用 `@` 符号引用文件或文件夹，AI 会读取其内容作为上下文。
- **斜杠命令**：使用 `/` 命令执行项目扫描、上下文管理等操作。

### 代码变更

AI 生成的代码变更会以 diff 视图展示，你可以：

- **审查变更**：逐行查看 AI 建议的修改内容。
- **接受或拒绝**：选择性地应用部分或全部变更。
- **回退操作**：对已应用的变更进行回退。

### 集成 MCP

VS Code 扩展同样支持 MCP 集成，你可以在项目中配置 MCP 服务器来扩展 AI 的能力。

## 与 CLI 的区别

| 特性 | VS Code 扩展 | CLI |
| --- | --- | --- |
| 使用环境 | VS Code 编辑器内 | 终端 |
| 交互方式 | 图形化聊天面板 | 命令行对话 |
| 代码变更 | diff 视图，支持回退 | 直接修改文件 |
| 文件引用 | @ 引用，图形化选择 | @ 引用，路径补全 |
| Shell 命令 | AI 代为执行 | 支持 Shell 模式直接执行 |
| 会话管理 | 面板内管理 | /sessions 命令管理 |

两种方式可以按需使用，互不冲突。CLI 更适合终端重度用户和自动化场景，VS Code 扩展更适合习惯图形化操作的开发者。
