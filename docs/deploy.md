# 部署与 CI

CueLint 是本地 CLI，没有服务端、数据库、容器或定时任务。部署就是把 Python 包装到用户机器上。

## 安装方式

```bash
# 推荐：隔离环境
pipx install .

# 当前用户
pip install --user .

# 开发
pip install -e '.[test]'
```

要求 Python 3.11+。没有系统级依赖；不需要 ffmpeg、浏览器或字体包。

## CI

`.github/workflows/ci.yml` 在 push 和 pull request 上跑 Python 3.11、3.12、3.13 的测试矩阵；在 `v*` 标签上额外校验版本号一致、跑完整测试、构建 sdist/wheel。CI 不联网跑业务逻辑，测试自身也不会发起网络请求。

## 本地发布前

```bash
python -m pytest
python -m build --sdist --wheel
python -m venv /tmp/cuelint-check
/tmp/cuelint-check/bin/pip install dist/cuelint-0.1.0-py3-none-any.whl
/tmp/cuelint-check/bin/cuelint --version
git tag v0.1.0
```

标签只在本地创建；本项目不配置 remote，也不自动发布到 PyPI。要发布时，由维护者自己添加 remote、推送和上传，见根目录 README 的“发布前还要做什么”。

## 回滚

CLI 没有持久状态；回滚就是 `pipx install cuelint==<旧版本>`，或重新安装旧 wheel。报告和 `.fixed` 文件是普通文件，不会被工具追踪。
