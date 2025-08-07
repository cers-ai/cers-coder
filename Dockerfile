# CERS Coder Dockerfile
# 基于Python 3.12的官方镜像
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 设置环境变量
ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 创建非root用户
RUN useradd --create-home --shell /bin/bash cers && \
    chown -R cers:cers /app
USER cers

# 复制requirements文件
COPY --chown=cers:cers requirements.txt requirements-dev.txt ./

# 安装Python依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 复制源代码
COPY --chown=cers:cers src/ ./src/
COPY --chown=cers:cers pyproject.toml ./

# 安装项目
RUN pip install --no-cache-dir --user -e .

# 创建必要的目录
RUN mkdir -p /app/workspace /app/out /app/state /app/memory /app/logs

# 设置PATH
ENV PATH="/home/cers/.local/bin:$PATH"

# 暴露端口（如果需要Web界面）
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# 默认命令
CMD ["cers-coder", "--help"]
