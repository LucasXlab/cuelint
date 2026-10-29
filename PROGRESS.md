# 进度

更新时间：2026-10-29

## 已完成

- 阶段 1：`docs/选题.md`。8 个候选、公开痛点证据、4 个通过门槛的候选各读 2 个竞品、打分，选定 CueLint（字幕质检与修复）。
- 参照仓库：`notes/参照.md`，28 条可照搬做法，每个阶段开工前重读。
- 阶段 2：`SPEC.md`、`DESIGN.md`、`docs/external-apis.md` 初稿。

## 进行中

- 阶段 2：独立子代理审稿；按审稿意见修改 SPEC 和 DESIGN；等待用户回复“继续”。

## 下一步

- 阶段 3：搭地基（数据模型、解析器、规则、profile、错误格式、测试辅助），再逐功能实现 check/fix/report/CLI。
- 阶段 4：从零安装、10 遍真实使用、3 个角度独立审查、截图。
- 阶段 5：README、文档、CI、LICENSE、CHANGELOG、launch 材料、v0.1.0 标签。

## 已知问题

- 审稿模式开启：阶段 2 完成后必须停一次，等用户回复。
- 选题阶段没有可用的 web_search（接口 401），证据全部通过 GitHub API、Hacker News Algolia 和直接抓取公开页面取得；已在 `docs/选题.md` 写明日期和方法。
