# C1  いまの構成（6 タスクが同じ tracelog）（NFSv3・6 タスク・250 秒）

- 書いた行（全タスク）: 5998 / 正しいファイルに残った: 842（14.0%）/ 別の時間帯のファイルに入った: 239（4.0%）/ 消えた: 4917（82.0%）
- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 597 行 / 残った 597 行

## タスクごと

| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 1001 | 127 | 0 | 874 | 2 | 4 | 100/100 |
| T2 | 997 | 243 | 0 | 754 | 2 | 4 | 99/99 |
| T3 | 1007 | 231 | 0 | 776 | 2 | 3 | 100/100 |
| T4 | 1003 | 241 | 0 | 762 | 2 | 4 | 100/100 |
| T5 | 998 | 0 | 0 | 998 | 2 | 4 | 99/99 |
| T6 | 992 | 0 | 239 | 753 | 2 | 3 | 99/99 |

## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）

- 08:05:00（UTC）順番: T6 → T3 → T5 → T2 → T1 → T4（境目からの遅れ ms: 45, 49, 61, 109, 113, 174）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=CURRENT, T5=STALE, T6=ARCHIVE
- 08:06:00（UTC）順番: T3 → T1 → T4 → T6 → T5 → T2（境目からの遅れ ms: 35, 51, 77, 79, 140, 267）
  実際: T1=STALE, T2=CURRENT, T3=STALE, T4=STALE, T5=STALE, T6=STALE
- 08:07:00（UTC）順番: T6 → T2 → T1 → T5 → T4 → T3（境目からの遅れ ms: 79, 128, 194, 266, 298, 328）
  実際: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE
- 08:08:00（UTC）順番: T3 → T6 → T4 → T2 → T5 → T1（境目からの遅れ ms: 38, 66, 81, 156, 169, 243）
  実際: T1=CURRENT, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE

## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）

- snap-170526.txt: T1=STALE, T2=STALE, T3=STALE, T4=CURRENT, T5=STALE, T6=CURRENT  集計 {'STALE': 4, 'CURRENT': 2}  サーバ側の実体と一致 5/6  不一致: T6（ツール CURRENT／実際 ARCHIVE）
- snap-170625.txt: T1=STALE, T2=CURRENT, T3=STALE, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-170725.txt: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-170825.txt: T1=CURRENT, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE  集計 {'CURRENT': 1, 'STALE': 5}  サーバ側の実体と一致 6/6

## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）

| 分（UTC） | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| 08-04 | 151/0/0/151 | 153/0/0/153 | 157/0/0/157 | 148/0/0/148 | 149/0/0/149 | 142/0/0/142 |
| 08-05 | 242/0/0/242 | 238/0/0/238 | 241/0/0/241 | 241/241/0/0 | 240/0/0/240 | 239/0/239/0 |
| 08-06 | 243/0/0/243 | 243/243/0/0 | 248/0/0/248 | 238/0/0/238 | 241/0/0/241 | 236/0/0/236 |
| 08-07 | 238/0/0/238 | 235/0/0/235 | 231/231/0/0 | 242/0/0/242 | 234/0/0/234 | 241/0/0/241 |
| 08-08 | 127/127/0/0 | 128/0/0/128 | 130/0/0/130 | 134/0/0/134 | 134/0/0/134 | 134/0/0/134 |

## ファイルごとの中身（どのタスクの・どの分の行か）

- logs/trace.log.2026-10-10-08-04: タスク {'T6': 239} / 分 {'2026-10-10-08-05': 239} / 大きさ 6931 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-08-05: タスク {'T4': 241} / 分 {'2026-10-10-08-05': 241} / 大きさ 6989 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-08-06: タスク {'T2': 243} / 分 {'2026-10-10-08-06': 243} / 大きさ 7047 / NUL 0 / 壊れた行 0
- logs/trace.log.2026-10-10-08-07: タスク {'T3': 231} / 分 {'2026-10-10-08-07': 231} / 大きさ 6699 / NUL 0 / 壊れた行 0
- logs/tracelog: タスク {'T1': 127} / 分 {'2026-10-10-08-08': 127} / 大きさ 3685 / NUL 0 / 壊れた行 0

## 標準エラーの例（Log4j2 StatusLogger）

### T1
```
2026-10-10T08:05:00.126806553Z main ERROR RollingFileManager /webapp/webapp9mf02/logs/tracelog Unable to close stream: java.io.IOException: Stale file handle
2026-10-10T08:05:03.219049699Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
2026-10-10T08:05:03.415828869Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
```
