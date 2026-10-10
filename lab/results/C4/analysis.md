# C4  仮説 1（動いている最中にファイルシステムを作り直す）（NFSv3・6 タスク・130 秒）

- 書いた行（全タスク）: 3126 / 正しいファイルに残った: 0（0.0%）/ 別の時間帯のファイルに入った: 0（0.0%）/ 消えた: 3126（100.0%）
- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 310 行 / 残った 0 行

## タスクごと

| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |
|---|---:|---:|---:|---:|---:|---:|---:|
| T1 | 521 | 0 | 0 | 521 | 2 | 2 | 52/0 |
| T2 | 518 | 0 | 0 | 518 | 2 | 2 | 51/0 |
| T3 | 531 | 0 | 0 | 531 | 2 | 2 | 53/0 |
| T4 | 519 | 0 | 0 | 519 | 2 | 2 | 51/0 |
| T5 | 527 | 0 | 0 | 527 | 2 | 2 | 52/0 |
| T6 | 510 | 0 | 0 | 510 | 2 | 2 | 51/0 |

## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）

- 10:06:00（UTC）順番: T1 → T4 → T3 → T6 → T5 → T2（境目からの遅れ ms: 9, 36, 41, 51, 71, 285）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE
- 10:07:00（UTC）順番: T2 → T6 → T5 → T1 → T3 → T4（境目からの遅れ ms: 32, 47, 64, 107, 169, 226）（作り直しの後）
  実際: T1=STALE, T2=STALE, T3=STALE, T4=STALE, T5=STALE, T6=STALE

- 作り直しの後に書いた行: トレース 1367 行中 0 行が残った / server.log 137 行中 0 行が残った

## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）

- snap-190725.txt: T1=MOUNTSTALE, T2=MOUNTSTALE, T3=MOUNTSTALE, T4=MOUNTSTALE, T5=MOUNTSTALE, T6=MOUNTSTALE  集計 {'MOUNTSTALE': 6}  サーバ側の実体と一致 6/6
- snap-before-recreate.txt: T1=STALE, T2=CURRENT, T3=STALE, T4=STALE, T5=STALE, T6=STALE  集計 {'STALE': 5, 'CURRENT': 1}  サーバ側の実体と一致 6/6

## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）

| 分（UTC） | T1 | T2 | T3 | T4 | T5 | T6 |
|---|---|---|---|---|---|---|
| 10-05 | 154/0/0/154 | 160/0/0/160 | 160/0/0/160 | 153/0/0/153 | 153/0/0/153 | 148/0/0/148 |
| 10-06 | 243/0/0/243 | 232/0/0/232 | 242/0/0/242 | 241/0/0/241 | 240/0/0/240 | 237/0/0/237 |
| 10-07 | 124/0/0/124 | 126/0/0/126 | 129/0/0/129 | 125/0/0/125 | 134/0/0/134 | 125/0/0/125 |

## ファイルごとの中身（どのタスクの・どの分の行か）


## 標準エラーの例（Log4j2 StatusLogger）

### T1
```
2026-10-10T10:06:03.080138364Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
2026-10-10T10:06:03.368336735Z main ERROR Unable to write to stream /webapp/webapp9mf02/logs/tracelog for appender A4
org.apache.logging.log4j.core.appender.AppenderLoggingException: Error writing to stream /webapp/webapp9mf02/logs/tracelog
Caused by: java.io.IOException: Stale file handle
```
