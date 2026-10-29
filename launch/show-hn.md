# Show HN draft

Title: Show HN: CueLint – check and fix SRT/VTT subtitles locally

Body:

I publish talking-head videos with auto-generated captions, and the annoying part is never the transcription accuracy. It is the presentation: a 100-character line, two cues overlapping by 100 ms, a cue that flashes for 500 ms, 20 characters per second.

CueLint is a small Python CLI that checks 13 subtitle rules and fixes what it can without changing the words:

- removes empty/duplicate cues and control characters
- trims overlaps, enforces minimum gaps and durations
- extends cues that are too fast when there is room
- rewraps long lines and splits overlong cues
- writes a self-contained HTML report for whatever it cannot fix

```bash
pipx install .
cuelint fix episode-07.srt --report report.html
```

No network, no upload, no account, no audio/video access. SRT and WebVTT only. Default profile is for Chinese speech (36 columns, 2 lines, 9 CPS); latin, presentation, and strict profiles are included.

The report is a single HTML file with before/after counts and per-cue status. It follows light/dark mode and works at 375 px. Tests are 88 pytest cases, offline, three consecutive runs.

I would especially like feedback from people who edit subtitles weekly: are the defaults wrong for your language or platform, and which unfixable case should be auto-fixed next?

GitHub: <link>
License: MIT
