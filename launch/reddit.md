# Reddit draft

Subreddits to consider: r/VideoEditing, r/editors, r/NewTubers (check each community's self-promotion rules first).

Title: I made a local CLI that checks and fixes SRT/VTT subtitles before publishing

Body:

I make talking-head videos with auto-generated captions. The captions are usually accurate but badly formatted: long lines, overlapping cues, 500 ms flashes, very high reading speed.

CueLint is a Python CLI that runs 13 checks and fixes the deterministic ones without rewriting the text. It also outputs an HTML report for issues it cannot fix safely.

- Local only: no upload, no account, no API, no audio/video reading.
- SRT and WebVTT.
- Four profiles; `cjk` default (36 columns, 2 lines, 9 CPS), plus `latin`, `presentation`, `strict`.
- `fix` is idempotent and never overwrites the input by default.
- 88 offline tests.

```bash
pipx install .
cuelint check episode.srt --report report.html
cuelint fix episode.srt --report report.html
```

It is early (0.1.0), MIT, and I am looking for concrete feedback: which rule is missing, which default is wrong for your workflow, and what makes the report hard to read.

Link: <link>
