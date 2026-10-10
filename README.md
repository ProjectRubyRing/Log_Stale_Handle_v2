# Log_Stale_Handle_v2 — 6 タスク・共有トレースログの「Stale file handle」解説・検証・道具

ECS Fargate の 6 タスクのフロントコンテナ（UBI 9.8・OpenJDK 21・JBoss EAP 8.1・Spring MVC）が、EFS 上の同じ
`/mnt/logs/front/logs/inter-api/tracelog` に Log4j 2.25.3 の RollingFile（毎時ロールオーバ）で書いていて、
`java.io.IOException: Stale file handle` が出た件の調査一式（v2）。前回の資料は隣の `Log_Stale_Handle`。

## 成果物

| ファイル | 内容 |
|---|---|
| `ECS_EFS_StaleFileHandle_6タスク_完全解説_v2.xlsx` | 解説（Meiryo UI・モノトーン、17 シート＋表紙） |
| `ECS_EFS_StaleFileHandle_6タスク_完全解説_v2.md` | 同じ本文の Markdown 版 |
| `tools/tracelog-fd-check.sh` | 各タスクの中で、Java が書いているトレースログの実体を CURRENT／ARCHIVE／STALE で判定する（読むだけ） |
| `lab/` | Docker で NFS サーバ＋6 タスクを立てて再現する実験（`run_lab6.sh`・`analyze.py`・結果） |
| `build/` | 資料の生成（本文は `content.py`・`ch_a.py`・`ch_a5.py`・`ch_b.py`・`ch_c.py`） |
| `tests/tools/verify_excel_com.ps1` | 生成した Excel を実物の Excel（COM）で開いて確認し、PDF と画像を作る |

## 結論（要約）

- **原因は仮説 2**：6 タスクの Log4j2 が同じ tracelog をそれぞれ毎時ロールオーバし、後のタスクが前のタスクのファイルを
  「空なら削除・中身があれば同じ名前の保存ファイルを上書き」で消す。消された実体に書いていたタスクに EFS が STALE を返す。
- **仮説 1（EFS の作り直し）は今回の主因ではない**：作り直すとマウント全体が壊れ、同じディレクトリの下の `mid/{タスクID}`
  にある JBoss のログも書けなくなる（実験 C4）。今回は JBoss のログが無事。
- **1 タスクだけ正常は毎時起きる**：最後にロールオーバしたタスクだけが正しく書ける（実験の全 12 回の境目で確認）。
- **ヘルスチェック API（Spring MVC）が 200 なのは握りつぶしではない**：A4 の `ignoreExceptions=true`（既定）で、
  例外は Log4j2 の中で止まり Controller に届かない。
- **対策**：`-Diwin.log` を JBoss と同じ `mid/{タスクID}` に向ける（Log4j2 の設定は同じ。実験 C3 で Stale 0・欠け 0）。

## 作り直し・再実行

```bash
# 資料（Excel と Markdown）を作る
python -X utf8 build/build_docs.py

# 再現実験（約 20 分。Docker の --privileged が必要）
bash lab/run_lab6.sh            # C1〜C4
python -X utf8 lab/analyze.py lab/results/C1

# Excel を実物の Excel で確認（Windows）
powershell -NoProfile -ExecutionPolicy Bypass -File tests/tools/verify_excel_com.ps1 \
  -Path ECS_EFS_StaleFileHandle_6タスク_完全解説_v2.xlsx -OutDir tests/out -Capture "00_表紙,05_動作イメージ:1-60"
```

## 注意

- 実験のサーバは EFS ではなく Linux の knfsd。EFS の「別のクライアントに消された実体に STALE を返す」振る舞いは NFSv3 で再現した
  （根拠は EFS 側の技術者の LKML 投稿と、本番の例外そのもの）。
- `lab/results_run1`・`lab/results_run2` は旧い配置（`/mnt/logs/front/inter-api/logs`）での 1・2 回目の結果。3 回目（`lab/results`）が本番と同じ配置。
