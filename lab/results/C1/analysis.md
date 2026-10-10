# C1  いまの構成（6 タスクが同じ tracelog）（NFSv3・6 タスク・250 秒）

- 書いた行（全タスク）: 5998 / 正しいファイルに残った: 1020（17.0%）/ 別の時間帯のファイルに入った: 0（0.0%）/ 消えた: 4978（83.0%）
- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 597 行 / 残った 597 行

## タスクごと

| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 1001 | 0 | 0 | 1001 | 2 | 4 | 100/100 |
| T2 | 997 | 0 | 0 | 997 | 2 | 4 | 99/99 |
| T3 | 1007 | 646 | 0 | 361 | 2 | 2 | 100/100 |
| T4 | 1003 | 133 | 0 | 870 | 2 | 3 | 100/100 |
| T5 | 998 | 0 | 0 | 998 | 2 | 4 | 99/99 |
| T6 | 992 | 241 | 0 | 751 | 2 | 3 | 99/99 |

## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）

- 09:52:00（UTC）順番: T1 → T2 → T4 → T5 → T6 → T3（境目からの遅れ ms: 1, 86, 118, 165, 194, 296）
  実際: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE
- 09:53:00（UTC）順番: T5 → T6 → T2 → T4 → T1 → T3（境目からの遅れ ms: 0, 7, 82, 112, 223, 260）
  実際: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE
- 09:54:00（UTC）順番: T1 → T4 → T2 → T5 → T3 → T6（境目からの遅れ ms: 71, 123, 127, 128, 176, 232）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT
- 09:55:00（UTC）順番: T5 → T3 → T2 → T1 → T6 → T4（境目からの遅れ ms: 26, 113, 128, 129, 210, 282）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=CURRENT, T5=STALE, T6=STALE

## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）

- snap-185225.txt: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-185325.txt: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-185425.txt: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=CURRENT  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6
- snap-185525.txt: T1=STALE, T2=STALE, T3=STALE, T4=CURRENT, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6

## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）

| 分（UTC） | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| 09-51 | 151/0/0/151 | 154/0/0/154 | 158/158/0/0 | 149/0/0/149 | 150/0/0/150 | 143/0/0/143 |
| 09-52 | 243/0/0/243 | 237/0/0/237 | 241/241/0/0 | 241/0/0/241 | 239/0/0/239 | 239/0/0/239 |
| 09-53 | 242/0/0/242 | 244/0/0/244 | 247/247/0/0 | 237/0/0/237 | 241/0/0/241 | 236/0/0/236 |
| 09-54 | 238/0/0/238 | 235/0/0/235 | 232/0/0/232 | 243/0/0/243 | 234/0/0/234 | 241/241/0/0 |
| 09-55 | 127/0/0/127 | 127/0/0/127 | 129/0/0/129 | 133/133/0/0 | 134/0/0/134 | 133/0/0/133 |

## ファイルごとの中身（どのタスクの・どの分の行か）

- trace.log.2026-10-10-09-51: タスク {'T3': 158} / 分 {'2026-10-10-09-51': 158} / 大きさ 4474 / NUL 0 / 壊れた行 0
- trace.log.2026-10-10-09-52: タスク {'T3': 241} / 分 {'2026-10-10-09-52': 241} / 大きさ 6989 / NUL 0 / 壊れた行 0
- trace.log.2026-10-10-09-53: タスク {'T3': 247} / 分 {'2026-10-10-09-53': 247} / 大きさ 7163 / NUL 0 / 壊れた行 0
- trace.log.2026-10-10-09-54: タスク {'T6': 241} / 分 {'2026-10-10-09-54': 241} / 大きさ 6989 / NUL 0 / 壊れた行 0
- tracelog: タスク {'T4': 133} / 分 {'2026-10-10-09-55': 133} / 大きさ 3861 / NUL 0 / 壊れた行 0

## 標準エラーの例（Log4j2 StatusLogger）

### T1
```
2026-10-10T09:52:03.092700893Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
2026-10-10T09:52:03.290893632Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
```
