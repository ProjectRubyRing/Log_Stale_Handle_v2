# C4  仮説 1（動いている最中にファイルシステムを作り直す）（NFSv3・6 タスク・130 秒）

- 書いた行（全タスク）: 3130 / 正しいファイルに残った: 0（0.0%）/ 別の時間帯のファイルに入った: 0（0.0%）/ 消えた: 3130（100.0%）
- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 311 行 / 残った 0 行

## タスクごと

| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 521 | 0 | 0 | 521 | 2 | 2 | 52/0 |
| T2 | 521 | 0 | 0 | 521 | 2 | 2 | 52/0 |
| T3 | 532 | 0 | 0 | 532 | 2 | 3 | 53/0 |
| T4 | 519 | 0 | 0 | 519 | 2 | 2 | 51/0 |
| T5 | 527 | 0 | 0 | 527 | 2 | 2 | 52/0 |
| T6 | 510 | 0 | 0 | 510 | 2 | 2 | 51/0 |

## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）

- 08:14:00（UTC）順番: T6 → T4 → T2 → T5 → T1 → T3（境目からの遅れ ms: 73, 92, 108, 137, 227, 303）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE
- 08:15:00（UTC）順番: T6 → T2 → T1 → T3 → T4 → T5（境目からの遅れ ms: 32, 65, 127, 134, 140, 286）（作り直しの後）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE

- 作り直しの後に書いた行: トレース 1424 行中 0 行が残った / server.log 142 行中 0 行が残った

## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）

- snap-171525.txt: T1=NOFD, T2=NOFD, T3=NOFD, T4=NOFD, T5=NOFD, T6=NOFD  集計 {'NOFD': 6}  サーバ側の実体と一致 6/6
- snap-before-recreate.txt: T1=STALE, T2=STALE, T3=CURRENT, T4=STALE, T5=CURRENT, T6=STALE  集計 {'STALE': 4, 'CURRENT': 2}  サーバ側の実体と一致 5/6  不一致: T5（ツール CURRENT／実際 ARCHIVE）

## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）

| 分（UTC） | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| 08-13 | 153/0/0/153 | 158/0/0/158 | 160/0/0/160 | 152/0/0/152 | 152/0/0/152 | 146/0/0/146 |
| 08-14 | 242/0/0/242 | 235/0/0/235 | 241/0/0/241 | 241/0/0/241 | 241/0/0/241 | 238/0/0/238 |
| 08-15 | 126/0/0/126 | 128/0/0/128 | 131/0/0/131 | 126/0/0/126 | 134/0/0/134 | 126/0/0/126 |

## ファイルごとの中身（どのタスクの・どの分の行か）


## 標準エラーの例（Log4j2 StatusLogger）

### T1
```
2026-10-10T08:14:03.276496542Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
2026-10-10T08:14:03.402451314Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
```
