# 进度

更新时间：2026-10-29

## 已完成

- 阶段 1：`docs/选题.md`。8 个候选、公开痛点证据、4 个通过门槛的候选各读 2 个竞品、打分，选定 CueLint（字幕质检与修复）。
- 参照仓库：`notes/参照.md`，28 条可照搬做法，每个阶段开工前重读。
- 阶段 2：`SPEC.md`、`DESIGN.md`、`docs/external-apis.md`。独立子代理审稿 30 条，全部逐条处理。
- 阶段 3：`src/cuelint/` 完成解析、13 条规则、修复流水线、CLI、TOML 配置、ANSI 颜色、自包含 HTML 报告。
- 测试：88 个 pytest 用例，连续三遍全部通过；原始输出在 `notes/test-runs.txt`。
- 仓库内提交，未配置 remote，未推送。

## 已完成（阶段 4/5）

- 从空目录克隆、venv、`pip install .` 安装成功；记录在 `notes/安装实录.md`。
- 11 次真实使用（含 5 条失败路径），记录在 `notes/真实使用.md`。
- 三路独立审查（新用户、安全/数据、正确性）发现并修复；记录在 `notes/审查记录.md`。
- 双语 README、功能/开发/偏差/部署文档、CI、MIT LICENSE、CHANGELOG、.env.example、launch 草稿、浅色/深色/375px 截图。
- 最终 113 个 pytest 用例，连续三遍通过；记录在 `notes/test-runs.txt`。
- 本地提交和 `v0.1.0` 标签；没有 remote，没有推送。

## 已知问题

- 选题阶段 web_search 接口 401，证据改用 GitHub API、Hacker News Algolia 和直接抓取公开页面；方法和日期已写在 `docs/选题.md`。
- 规格里“平台认证阈值”刻意没有声称，profile 数字是 CueLint 默认值，README 会写明。
- `notes/research/` 是另一个并行会话留下的研究材料，未纳入本项目，也未删除。
