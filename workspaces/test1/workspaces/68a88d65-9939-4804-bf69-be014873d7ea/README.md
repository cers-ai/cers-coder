# 项目工作空间

这是一个CERS Coder项目工作空间。

## 目录结构

- `input/` - 输入文件目录（放置0.request.md等需求文件）
- `output/` - 输出文件目录
  - `src/` - 生成的源代码
  - `test/` - 生成的测试代码
  - `docs/` - 生成的文档
  - `build/` - 构建产物
  - `review/` - 审查报告
- `state/` - 项目状态文件
- `records/` - 操作记录
- `memory/` - 智能体记忆
- `logs/` - 日志文件
- `temp/` - 临时文件
- `backup/` - 备份文件

## 使用方法

1. 将项目需求文件放入 `input/` 目录
2. 在工作空间根目录运行 `cers-coder start`
3. 查看 `output/` 目录中的生成结果

创建时间: 2025-08-08 08:09:55
