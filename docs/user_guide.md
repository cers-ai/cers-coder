# CERS Coder 用户指南

## 1. 快速入门

### 1.1 系统要求

- **操作系统**: Windows 10+, macOS 10.15+, Linux (Ubuntu 18.04+)
- **Python**: 3.12 或更高版本
- **内存**: 最少 8GB RAM (推荐 16GB+)
- **存储**: 至少 10GB 可用空间
- **网络**: 用于下载模型 (首次使用)

### 1.2 安装方式选择

| 方式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| Docker | 快速体验、生产部署 | 环境隔离、一键启动 | 需要Docker知识 |
| 本地安装 | 开发调试、深度定制 | 灵活配置、易调试 | 环境配置复杂 |
| 源码安装 | 二次开发、贡献代码 | 完全控制、可修改 | 需要开发经验 |

## 2. Docker 部署指南

### 2.1 环境准备

```bash
# 安装 Docker 和 Docker Compose
# Ubuntu/Debian
sudo apt update
sudo apt install docker.io docker-compose

# CentOS/RHEL
sudo yum install docker docker-compose

# macOS (使用 Homebrew)
brew install docker docker-compose

# Windows
# 下载并安装 Docker Desktop
```

### 2.2 快速启动

```bash
# 1. 克隆项目
git clone https://github.com/your-org/cers-coder.git
cd cers-coder

# 2. 创建必需的输入文件
cp 0.request.md.example 0.request.md

# 3. 编辑需求文件
nano 0.request.md  # 或使用你喜欢的编辑器

# 4. 启动服务 (简化版)
docker-compose -f docker-compose.simple.yaml up -d

# 5. 查看服务状态
docker-compose -f docker-compose.simple.yaml ps

# 6. 进入容器
docker exec -it cers-coder-app bash

# 7. 开始开发
cers-coder start
```

### 2.3 完整版部署

```bash
# 启动完整版 (包含监控、数据库等)
docker-compose up -d

# 访问监控面板
# Grafana: http://localhost:3000 (admin/admin)
# Prometheus: http://localhost:9090
```

## 3. 本地安装指南

### 3.1 安装 Ollama

```bash
# macOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows
# 从 https://ollama.ai/download 下载安装包

# 启动 Ollama 服务
ollama serve

# 验证安装
ollama --version
```

### 3.2 拉取推荐模型

```bash
# 基础模型 (必需)
ollama pull llama3:8b

# 代码专用模型 (推荐)
ollama pull deepseek-coder:6.7b

# 轻量级模型 (资源受限时)
ollama pull phi:latest

# 查看已安装模型
ollama list
```

### 3.3 安装 CERS Coder

```bash
# 1. 克隆项目
git clone https://github.com/your-org/cers-coder.git
cd cers-coder

# 2. 创建虚拟环境
python -m venv venv

# 3. 激活虚拟环境
# Linux/macOS
source venv/bin/activate
# Windows
venv\Scripts\activate

# 4. 升级 pip
python -m pip install --upgrade pip

# 5. 安装依赖
pip install -r requirements.txt

# 6. 安装项目
pip install -e .

# 7. 验证安装
cers-coder --version
```

### 3.4 环境配置

```bash
# 1. 复制配置文件
cp .env.example .env

# 2. 编辑配置
nano .env
```

**重要配置项**:
```bash
# Ollama 配置
OLLAMA_HOST=http://localhost:11434
OLLAMA_DEFAULT_MODEL=llama3:8b

# 目录配置
WORK_DIR=./workspace
OUTPUT_DIR=./out
STATE_DIR=./state

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/cers-coder.log
```

## 4. 使用流程

### 4.1 准备输入文件

#### 必需文件: 0.request.md

```markdown
# 项目需求说明

## 🧱 项目名称
我的智能助手应用

## 🎯 项目目标
开发一个基于AI的个人助手应用，帮助用户管理日程、任务和提醒。

## 🔧 系统特性与设计原则
* **智能对话**: 支持自然语言交互
* **任务管理**: 创建、编辑、删除任务
* **日程安排**: 智能日程规划
* **提醒功能**: 基于时间和位置的提醒

## 🧩 智能体构成与职责定义
| 智能体 | 职责 |
|--------|------|
| PM智能体 | 项目管理和协调 |
| 需求分析智能体 | 分析用户需求 |
| 架构设计智能体 | 设计系统架构 |
| 编码工程师智能体 | 实现核心功能 |

## 📦 项目输出要求
| 目录/文件 | 描述 |
|-----------|------|
| `out/src/` | 源代码文件 |
| `out/test/` | 测试脚本 |
| `out/docs/` | 项目文档 |
| `out/build/` | 构建配置 |
```

#### 可选文件

**1.rule.md** - 编码规范:
```markdown
# 编码规范

## 代码风格
- 使用 Python 3.12+
- 遵循 PEP 8 规范
- 使用类型注解

## 命名规范
- 类名使用 PascalCase
- 函数名使用 snake_case
- 常量使用 UPPER_CASE

## 文档要求
- 所有公共函数必须有文档字符串
- 使用 Google 风格的文档字符串
```

**3.assets.md** - 已有资产:
```markdown
# 已有资产

## 数据库设计
已有用户表和任务表的设计方案...

## API接口
已定义的REST API接口规范...

## UI设计
已完成的界面设计稿...
```

**4.env.md** - 环境要求:
```markdown
# 环境要求

## 运行环境
- Python 3.12+
- FastAPI 框架
- PostgreSQL 数据库
- Redis 缓存

## 部署要求
- 支持 Docker 容器化
- 支持 Kubernetes 部署
- 需要 HTTPS 支持
```

### 4.2 启动开发

```bash
# 检查系统状态
cers-coder status

# 启动新项目
cers-coder start --project-name "我的智能助手"

# 或者简单启动
cers-coder start
```

### 4.3 监控进度

系统启动后会显示实时进度：

```
🚀 初始化 CERS Coder 系统
✅ 状态管理器初始化完成
✅ Ollama连接成功
✅ 模型配置加载完成
✅ 工作流控制器初始化完成
✅ 智能体初始化完成

📋 开始项目开发流程
✅ 成功解析文件: 0.request.md

📊 开始监控项目进度...
进度: 15.2% (2/13 任务完成)
```

### 4.4 中断和恢复

```bash
# 中断开发 (Ctrl+C)
^C⏸️  用户中断，正在停止...

# 查看项目列表
cers-coder list

# 恢复项目
cers-coder resume <project-id>
```

### 4.5 查看结果

开发完成后，检查输出目录：

```bash
# 查看输出结构
tree out/

out/
├── src/                 # 源代码
│   ├── main.py
│   ├── models/
│   ├── api/
│   └── utils/
├── test/               # 测试代码
│   ├── test_main.py
│   └── test_api.py
├── docs/               # 文档
│   ├── README.md
│   ├── api.md
│   └── deployment.md
├── build/              # 构建配置
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
├── logs/               # 开发日志
└── review/             # 审查报告
```

## 5. 高级功能

### 5.1 自定义工作流

通过 `2.mcp.md` 文件自定义开发流程：

```markdown
# 自定义工作流

## 阶段配置
- 需求分析: 2天
- 原型设计: 1天  
- 详细设计: 2天
- 编码实现: 5天
- 测试验证: 2天

## 并发设置
- 最大并发智能体: 3
- 任务超时时间: 600秒

## 质量门禁
- 代码覆盖率 > 80%
- 静态分析无严重问题
- 性能测试通过
```

### 5.2 模型配置

```bash
# 查看可用模型
ollama list

# 切换默认模型
export OLLAMA_DEFAULT_MODEL=deepseek-coder:6.7b

# 为特定智能体配置模型
# 在 .env 文件中设置
CODING_AGENT_MODEL=deepseek-coder:6.7b
ANALYSIS_AGENT_MODEL=llama3:8b
```

### 5.3 项目模板

```bash
# 使用内置模板
cers-coder create --template web-app
cers-coder create --template api-service
cers-coder create --template data-pipeline

# 创建自定义模板
mkdir templates/my-template
# 编辑模板文件...
cers-coder create --template my-template
```

## 6. 故障排除

### 6.1 常见问题

**问题**: Ollama 连接失败
```bash
# 检查 Ollama 服务状态
ollama list

# 重启 Ollama 服务
sudo systemctl restart ollama  # Linux
brew services restart ollama   # macOS

# 检查端口占用
netstat -tlnp | grep 11434
```

**问题**: 内存不足
```bash
# 使用轻量级模型
export OLLAMA_DEFAULT_MODEL=phi:latest

# 限制并发智能体数量
export MAX_CONCURRENT_AGENTS=1
```

**问题**: 生成质量不佳
```bash
# 使用更大的模型
ollama pull llama3:70b
export OLLAMA_DEFAULT_MODEL=llama3:70b

# 调整生成参数
export MODEL_TEMPERATURE=0.3
export MODEL_MAX_TOKENS=4096
```

### 6.2 日志分析

```bash
# 查看实时日志
tail -f logs/cers-coder.log

# 搜索错误信息
grep -i error logs/cers-coder.log

# 查看特定智能体日志
grep "coding_agent" logs/cers-coder.log
```

### 6.3 性能优化

```bash
# 清理旧状态文件
cers-coder cleanup --days 30

# 优化模型缓存
ollama prune

# 监控资源使用
htop  # 或 top
nvidia-smi  # GPU使用情况
```

## 7. 最佳实践

### 7.1 需求编写

- **明确具体**: 避免模糊的描述
- **结构化**: 使用标准的Markdown格式
- **完整性**: 包含功能和非功能需求
- **可验证**: 提供明确的验收标准

### 7.2 项目管理

- **定期检查**: 监控开发进度
- **及时干预**: 发现问题及时处理
- **版本控制**: 使用Git管理生成的代码
- **备份重要**: 定期备份项目状态

### 7.3 质量保证

- **代码审查**: 仔细检查生成的代码
- **测试验证**: 运行生成的测试用例
- **文档完善**: 补充必要的文档说明
- **持续改进**: 根据结果优化需求描述

## 8. 社区支持

### 8.1 获取帮助

- **GitHub Issues**: 报告问题和建议
- **讨论区**: 技术交流和经验分享
- **文档**: 查阅详细技术文档
- **示例**: 参考项目示例

### 8.2 贡献代码

- **Fork项目**: 创建自己的分支
- **提交PR**: 贡献代码和文档
- **报告问题**: 帮助改进系统
- **分享经验**: 编写使用教程

欢迎加入CERS Coder社区，一起构建更智能的开发工具！
