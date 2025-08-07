# CERS Coder - 极简智能开发Agent系统

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Docker](https://img.shields.io/badge/docker-supported-blue.svg)](docker-compose.yaml)

## 🎯 项目简介

CERS Coder（极简智能体开发系统）是一个本地部署的多智能体协同开发平台，参考 Claude Code 的开发交互模式，实现了一个只通过终端入口+本地文件驱动的自动化开发环境。用户无需使用 GUI 或复杂指令，仅通过准备项目目录下的标准输入文件，即可由智能体团队完成从需求分析到项目交付的全流程开发。

## ✨ 核心特性

- **🚀 极简启动**: 项目以终端窗口作为唯一入口，用户无需复杂交互
- **🤖 多智能体协同**: 8个专业智能体分工协作，具备类组织化开发能力
- **📁 文件驱动**: 系统仅通过读取根目录下的 Markdown 文件进行初始化
- **🔄 断点续开发**: 支持中途中断后自动加载状态并恢复任务执行
- **🏠 本地部署**: 所有推理过程依赖本地部署的 Ollama LLM
- **📊 全程可追溯**: 全过程输出包括中间产物、日志、测试报告、审查文档
- **🐳 容器化部署**: 支持 Docker 和 docker-compose 一键部署

## 🧩 智能体架构

| 智能体 | 职责 |
|--------|------|
| **PM 智能体** | 拆分任务阶段，组织各Agent工作，控制进度与输出对齐 |
| **需求分析智能体** | 结构化提取业务需求，生成功能模型与用例文档 |
| **架构设计智能体** | 输出系统模块图、接口定义、数据结构与技术选型 |
| **编码工程师智能体** | 基于架构完成代码开发，模块化输出，包含注释与文档 |
| **测试智能体** | 自动生成测试用例与脚本，运行测试并反馈异常 |
| **构建部署智能体** | 生成构建脚本（如 Dockerfile、CI），输出可执行程序 |
| **文档生成智能体** | 自动输出开发说明、接口文档、架构图、用户指南等 |
| **审查智能体** | 对阶段性成果进行一致性审查，发现问题并提出优化建议 |

## 📋 标准输入文件

| 文件名 | 必选 | 内容描述 |
|--------|------|----------|
| `0.request.md` | ✅ | 功能需求、目标、输出范围 |
| `1.rule.md` | ❌ | 编码风格、命名规范、模块划分约束等规则 |
| `2.mcp.md` | ❌ | 自定义开发流程与智能体间通信协议 |
| `3.assets.md` | ❌ | 提供已有资产：接口说明、已有模型、已有代码等 |
| `4.env.md` | ❌ | 描述运行平台、语言环境、依赖库要求等 |

## 🚀 快速开始

### 方式一：Docker 部署（推荐）

1. **克隆项目**
```bash
git clone https://github.com/your-org/cers-coder.git
cd cers-coder
```

2. **准备输入文件**
```bash
# 创建必需的输入文件
cp 0.request.md.example 0.request.md
# 编辑 0.request.md 文件，描述你的项目需求
```

3. **启动服务**
```bash
# 使用简化版配置
docker-compose -f docker-compose.simple.yaml up -d

# 或使用完整版配置（包含监控等服务）
docker-compose up -d
```

4. **进入容器并开始开发**
```bash
docker exec -it cers-coder-app bash
cers-coder start
```

### 方式二：本地安装

1. **环境要求**
- Python 3.12+
- Ollama (本地安装并运行)

2. **安装 Ollama**
```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# 下载并安装 Ollama for Windows

# 启动 Ollama 服务
ollama serve

# 拉取推荐模型
ollama pull llama3:8b
ollama pull deepseek-coder:6.7b
```

3. **安装 CERS Coder**
```bash
git clone https://github.com/your-org/cers-coder.git
cd cers-coder

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
pip install -e .
```

4. **配置环境**
```bash
cp .env.example .env
# 编辑 .env 文件，配置 Ollama 地址等参数
```

5. **开始使用**
```bash
# 检查系统状态
cers-coder status

# 启动新项目
cers-coder start --project-name "我的项目"

# 列出所有项目
cers-coder list

# 恢复项目
cers-coder resume <project-id>
```

## 📖 使用指南

### 1. 准备项目需求

创建 `0.request.md` 文件，描述你的项目需求：

```markdown
# 我的项目需求

## 项目名称
智能任务管理系统

## 项目目标
构建一个基于AI的任务管理系统，帮助用户智能化管理日常任务。

## 功能需求
- 任务创建和编辑
- 智能任务分类
- 优先级自动排序
- 进度跟踪
- 报告生成

## 技术要求
- 使用 Python + FastAPI
- 前端使用 React
- 数据库使用 PostgreSQL
- 支持 Docker 部署
```

### 2. 启动开发流程

```bash
cers-coder start
```

系统将自动：
1. 解析输入文件
2. 生成项目计划
3. 启动智能体团队
4. 执行开发流程
5. 输出完整项目

### 3. 监控进度

系统会实时显示开发进度，包括：
- 当前执行阶段
- 任务完成情况
- 智能体状态
- 错误和警告信息

### 4. 查看输出

开发完成后，所有产出将保存在 `out/` 目录：

```
out/
├── src/          # 源代码文件
├── test/         # 测试脚本与报告
├── docs/         # 架构文档、接口文档、用户说明
├── build/        # 构建产物，如可执行程序、镜像、配置
├── logs/         # 开发过程日志与交互记录
└── review/       # 审查报告与改进建议
```

## ⚙️ 配置说明

### 环境变量

```bash
# Ollama 配置
OLLAMA_HOST=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3:8b

# 目录配置
WORK_DIR=./workspace
OUTPUT_DIR=./out
STATE_DIR=./state
MEMORY_DIR=./memory

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/cers-coder.log

# 系统配置
MAX_CONCURRENT_AGENTS=3
AGENT_TIMEOUT=300
```

### 模型推荐

| 阶段 | 推荐模型 | 说明 |
|------|----------|------|
| 需求分析 | llama3:8b | 理解能力强，适合需求分析 |
| 架构设计 | llama3:8b | 逻辑思维清晰，适合架构设计 |
| 代码生成 | deepseek-coder:6.7b | 专业代码模型，生成质量高 |
| 测试编写 | deepseek-coder:6.7b | 熟悉测试框架和最佳实践 |
| 文档撰写 | llama3:8b | 文档组织能力强 |

## 🔧 高级功能

### 断点续开发

```bash
# 系统会自动保存状态，中断后可恢复
cers-coder resume <project-id>
```

### 自定义工作流

通过 `2.mcp.md` 文件自定义开发流程：

```markdown
# 自定义工作流

## 阶段定义
1. 需求分析 (2天)
2. 原型设计 (1天)
3. 详细设计 (2天)
4. 编码实现 (5天)
5. 测试验证 (2天)
6. 部署上线 (1天)

## 智能体协作规则
- PM智能体负责整体协调
- 需求分析智能体输出需求文档后，通知架构设计智能体
- 编码智能体完成模块后，自动触发测试智能体
```

### 项目模板

支持基于模板快速创建项目：

```bash
cers-coder create --template web-app --name "我的Web应用"
cers-coder create --template api-service --name "我的API服务"
cers-coder create --template data-pipeline --name "我的数据管道"
```

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出建议！

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🙏 致谢

- [Ollama](https://ollama.ai/) - 本地LLM运行时
- [Claude](https://claude.ai/) - 设计灵感来源
- [Rich](https://github.com/Textualize/rich) - 终端美化
- [FastAPI](https://fastapi.tiangolo.com/) - 现代Python Web框架

## 📞 联系我们

- 项目主页: https://www.cers-ai.cn/cers-coder
- 问题反馈: https://github.com/cers-ai/cers-coder/issues
- 讨论区: https://github.com/cers-ai/cers-coder/discussions

---

**让AI为你编程，让创意自由飞翔！** 🚀
