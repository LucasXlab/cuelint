# 示例字幕

`demo.zh.srt` 是一段虚构的中文口播字幕，故意包含重叠、停留过短、间隔过小、语速过快和行宽超限，用来演示检查与修复。

```bash
cuelint check examples/demo.zh.srt
cuelint fix examples/demo.zh.srt --report demo-report.html
```

`demo.zh.fixed.srt` 是运行结果，已被 `.gitignore` 忽略，不纳入版本库。示例内容为原创占位文本，不来自任何真实视频。
