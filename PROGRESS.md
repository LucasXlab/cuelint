# 进度

更新时间：2026-10-29

## 已完成

- 阶段 1：`docs/选题.md`。8 个候选、公开痛点证据、4 个通过门槛的候选各读 2 个竞品、打分，选定 CueLint（字幕质检与修复）。
- 参照仓库：`notes/参照.md`，28 条可照搬做法，每个阶段开工前重读。
- 阶段 2：`SPEC.md`、`DESIGN.md`、`docs/external-apis.md`。独立子代理审稿 30 条，全部逐条处理。
- 阶段 3：`src/cuelint/` 完成解析、13 条规则、修复流水线、CLI、TOML 配置、ANSI 颜色、自包含 HTML 报告。
- 测试：88 个 pytest 用例，连续三遍全部通过；原始输出在 `notes/test-runs.txt`。
- 仓库内提交，未配置 remote，未推送。

## 进行中

- 阶段 4：README 后从空目录安装、真实使用、截图、三路独立审查。

## 下一步

- 阶段 5：README/README_EN、docs/features、development、deviations、deploy、CI、LICENSE、CHANGELOG、.env.example、launch 材料、v0.1.0 标签和最终总结。

## 已知问题

- 选题阶段 web_search 接口 401，证据改用 GitHub API、Hacker News Algolia 和直接抓取公开页面；方法和日期已写在 `docs/选题.md`。
- 规格里“平台认证阈值”刻意没有声称，profile 数字是 CueLint 默认值，README 会写明。
- `notes/research/` 是另一个并行会话留下的研究材料，未纳入本项目，也未删除。
