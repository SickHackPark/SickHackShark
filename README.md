# SickHackShark

SickHackShark 是一个基于AI Agent智能体的CTF（Capture The Flag）网络安全竞赛自动化工具平台。它采用多Agent智能体架构，能够自动完成Web安全测试任务，包括信息收集、漏洞扫描、漏洞利用和flag获取等全过程。

## 项目简介

SickHackShark 设计用于自动化完成CTF网络安全竞赛中的Web挑战。系统采用模块化的多Agent架构，主要包括：

### 主要组件

1. **主Agent** - 协调整个任务流程，调度各个子Agent执行专门任务
2. **web-scout-subagent** - 负责Web应用的信息收集和侦察
3. **vuln-find-dig-and-flag-subagent** - 负责漏洞挖掘、利用和flag获取
4. **flag-exploit-subagent** - 专门用于已知漏洞的flag获取

### 核心功能

- 自动化Web应用侦察和信息收集
- 多种Web漏洞的自动检测和利用（如SQL注入、XSS、命令注入等）
- 智能flag搜索和验证
- Kali Linux工具集成
- 报告生成和结果管理

## 基于YAML的灵活Agent编排

SickHackShark通过YAML配置文件实现灵活的Agent编排，具有以下核心优势：

### 1. 高度可定制化
可根据不同CTF题目类型自由组合所需Agent，支持个性化任务配置。

### 2. 模块化架构
各Agent职责分明，独立开发维护，支持并行处理和动态调度。

### 3. 易于维护升级
配置驱动的设计使系统行为调整无需重新编译，支持版本管理和快速回滚。

### 4. 丰富中间件支持
内置模型降级、上下文管理等中间件，提升系统稳定性和容错能力。

通过这种基于 YAML 的灵活配置方式，SickHackShark 能够适应各种复杂多变的 CTF 挑战场景，为用户提供强大而灵活的自动化渗透测试能力。

## 运行方法

### 环境要求

- Docker
- Docker Compose

### 快速开始

1. 克隆项目仓库：
   ```bash
   git clone https://github.com/SickHackPark/SickHackShark.git
   cd SickHackShark
   ```

2. 配置环境变量：
   ```bash
   cp .env.example .env
   # 编辑 .env 文件，填入必要的API密钥等配置
   ```

   环境变量配置说明：
   - `LANGSMITH_PROJECT`: LangSmith项目名称，用于区分不同应用的追踪记录
   - `LANGSMITH_TRACING`: 是否启用LangSmith追踪功能
   - `LANGSMITH_API_KEY`: LangSmith平台的API密钥
   
   主模型配置：
   - `MAIN_OPENAI_API_KEY`: 主模型API密钥
   - `MAIN_OPENAI_BASE_URL`: 主模型API基础URL
   - `MAIN_OPENAI_MODEL`: 主模型名称
   - `MAIN_MODEL_TEMPERATURE`: 主模型温度参数，控制输出随机性
   
   备用模型配置：
   - `BACKUP_OPENAI_API_KEY`: 备用模型API密钥
   - `BACKUP_OPENAI_BASE_URL`: 备用模型API基础URL
   - `BACKUP_OPENAI_MODEL`: 备用模型名称
   - `BACKUP_MODEL_TEMPERATURE`: 备用模型温度参数

   Kali工具配置：
   - `KALI_API_BASE_URL`: Kali工具服务的基础URL

3. 构建并启动服务：
   ```bash
   make build
   make run
   ```

4. 访问服务：
   API服务请访问: `http://127.0.0.1:2024`
   UI服务请访问: `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

### 停止服务

```bash
make down
```

### 查看日志

```bash
make logs
```

## ctf_deepagents.yaml 编写规则

ctf_deepagents.yaml 是 SickHackShark 的核心配置文件，用于定义Agent的行为和交互规则。

### 配置结构

配置文件主要分为以下几个部分：

#### 1. system_prompt

定义主Agent的系统提示，包含整体任务指导和规则说明。

#### 2. filesystem_backend

配置文件系统后端：
```yaml
filesystem_backend:
  route: "/knowledge_base/"     # 路由路径
  root_dir: "/app/knowledge_base/"   # 根目录
  virtual_mode: false           # 是否启用虚拟模式
```

#### 3. middleware

中间件配置，用于处理Agent的上下文管理和优化：
```yaml
middleware:
  - type: "ModelFallbackMiddleware"
  - type: "ImportantNotesMiddleware"
  - type: "ContextEditingMiddleware"
    edits:
      - type: "LongChainWakeUp"
        max_consecutive_counts: 20
        important_tool_name: "write_important_notes"
        exclude_tools: ["write_todos"]
```

常用的中间件类型包括：

- `ModelFallbackMiddleware`: 模型降级中间件，当主模型无法正常工作时自动切换到备用模型
- `ImportantNotesMiddleware`: 重要笔记中间件，用于提取和保存关键信息
- `ContextEditingMiddleware`: 上下文编辑中间件，用于管理和优化Agent的上下文长度
  - `LongChainWakeUp`: 长链唤醒机制，防止在长任务链中丢失重要信息
  - `ClearToolUsesEdit`: 工具使用清理机制，定期清理历史工具调用记录以控制上下文长度

#### 4. subagents

定义子Agent的配置，每个子Agent包含以下属性：

- `name`: Agent名称
- `description`: Agent描述
- `system_prompt`: Agent的系统提示
- `tools`: Agent可用的工具列表
- `middleware`: Agent专用的中间件配置

##### 示例子Agent配置：

```yaml
- name: "web-scout-subagent"
  description: "专门用于主动探索Web应用程序，发现潜在的漏洞入口点和敏感信息泄露"
  system_prompt: |
    # 详细的系统提示内容
    # 可以包含多行文本
  tools:
    - "curl"
    - "execute_python_code_command"
  middleware:
    # 中间件配置
```

### 编写最佳实践

1. **系统提示设计**：
   - 明确Agent的职责和边界
   - 提供详细的工作流程说明
   - 包含必要的安全测试技巧和方法

2. **工具选择**：
   - 根据Agent职责选择合适的工具
   - 避免给予不必要的工具权限

3. **中间件配置**：
   - 合理设置上下文清理阈值
   - 使用适当的中间件优化性能

4. **命名规范**：
   - 使用有意义的名称和描述
   - 保持配置的一致性和可读性

### 子Agent职责划分

1. **web-scout-subagent**：
   - 负责Web应用侦察
   - 收集端点、参数、潜在漏洞等信息
   - 输出侦察报告供其他Agent使用

2. **vuln-find-dig-and-flag-subagent**：
   - 负责漏洞挖掘和利用
   - 一次专注于一种漏洞类型
   - 搜索和验证flag

3. **flag-exploit-subagent**：
   - 专门用于已知漏洞的flag获取
   - 在其他Agent确认漏洞但未找到flag时调用

通过合理配置ctf_deepagents.yaml，可以定制化SickHackShark的行为，适应不同类型的CTF挑战。