# C1  いまの構成（6 タスクが同じ tracelog）（NFSv3・6 タスク・250 秒）

- 書いた行（全タスク）: 5998 / 正しいファイルに残った: 856（14.3%）/ 別の時間帯のファイルに入った: 240（4.0%）/ 消えた: 4902（81.7%）
- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 597 行 / 残った 597 行

## タスクごと

| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 1001 | 0 | 0 | 1001 | 2 | 5 | 100/100 |
| T2 | 997 | 243 | 0 | 754 | 2 | 3 | 99/99 |
| T3 | 1007 | 0 | 0 | 1007 | 2 | 5 | 100/100 |
| T4 | 1003 | 0 | 0 | 1003 | 2 | 4 | 100/100 |
| T5 | 998 | 0 | 240 | 758 | 2 | 3 | 99/99 |
| T6 | 992 | 613 | 0 | 379 | 2 | 2 | 99/99 |

## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）

- 09:37:00（UTC）順番: T5 → T2 → T4 → T3 → T1 → T6（境目からの遅れ ms: 7, 96, 102, 151, 194, 274）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=ARCHIVE, T6=CURRENT
- 09:38:00（UTC）順番: T4 → T5 → T6 → T1 → T3 → T2（境目からの遅れ ms: 16, 75, 76, 128, 131, 241）
  実際: T1=STALE, T2=CURRENT, T3=STALE, T4=STALE, T5=STALE, T6=STALE
- 09:39:00（UTC）順番: T3 → T1 → T2 → T5 → T4 → T6（境目からの遅れ ms: 68, 78, 110, 223, 241, 316）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT
- 09:40:00（UTC）順番: T1 → T4 → T5 → T2 → T3 → T6（境目からの遅れ ms: 14, 32, 141, 151, 164, 308）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT

## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）

- snap-183726.txt: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=CURRENT, T6=CURRENT  集計 {'STALE': 4, 'CURRENT': 2}  サーバ側の実体と一致 5/6  不一致: T5（ツール CURRENT／実際 ARCHIVE）
- snap-183825.txt: T1=STALE, T2=CURRENT, T3=STALE, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-183925.txt: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-184025.txt: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6

## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）

| 分（UTC） | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| 09-36 | 150/0/0/150 | 153/0/0/153 | 157/0/0/157 | 148/0/0/148 | 149/0/0/149 | 143/0/0/143 |
| 09-37 | 242/0/0/242 | 238/0/0/238 | 241/0/0/241 | 241/0/0/241 | 240/0/240/0 | 239/239/0/0 |
| 09-38 | 242/0/0/242 | 243/243/0/0 | 247/0/0/247 | 238/0/0/238 | 241/0/0/241 | 236/0/0/236 |
| 09-39 | 238/0/0/238 | 235/0/0/235 | 232/0/0/232 | 242/0/0/242 | 234/0/0/234 | 241/241/0/0 |
| 09-40 | 129/0/0/129 | 128/0/0/128 | 130/0/0/130 | 134/0/0/134 | 134/0/0/134 | 133/133/0/0 |

## ファイルごとの中身（どのタスクの・どの分の行か）

- logs/trace.log.2026-10-10-09-36: タスク {'T5': 240} / 分 {'2026-10-10-09-37': 240} / 大きさ 6960 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-09-37: タスク {'T6': 239} / 分 {'2026-10-10-09-37': 239} / 大きさ 6931 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-09-38: タスク {'T2': 243} / 分 {'2026-10-10-09-38': 243} / 大きさ 7047 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-09-39: タスク {'T6': 241} / 分 {'2026-10-10-09-39': 241} / 大きさ 6989 / NUL 0 / 壊れた行 0
- logs/tracelog: タスク {'T6': 133} / 分 {'2026-10-10-09-40': 133} / 大きさ 3857 / NUL 0 / 壊れた行 0

## 標準エラーの例（Log4j2 StatusLogger）

### T1
```
2026-10-10T09:37:00.199597462Z main ERROR RollingFileManager /webapp/webapp9mf02/logs/tracelog Unable to close stream: java.io.IOException: Stale file handle
2026-10-10T09:37:03.439879295Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
2026-10-10T09:37:03.672765100Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
```
