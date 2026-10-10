# -*- coding: utf-8 -*-
"""11 恒久対策 / 12 運用回避 / 13 ヘルスチェック / 14 コマンド集 / 15 検証結果 / 16 用語集 / 17 参考資料"""
import lab_results as L

# ---------------------------------------------------------------------------
# 11 恒久対策
# ---------------------------------------------------------------------------
CH11 = {
    "name": "11_恒久対策", "no": "11", "title": "恒久対策：1 ファイル 1 書き手・正本を CloudWatch Logs に",
    "lead": "原則は「1 つのファイルに書くのは 1 つの JVM だけ」。JBoss のログ（mid/{タスクID}）で既にできていることを、トレースログにも当てはめる。",
    "blocks": [
        ("callout", "原則",
         "Log4j2 のロールオーバは、同じ JVM の中でしか調整されない。だから「書き手が 1 つ」なら、EFS の上でも安全に動く（再現実験 C3：6 タスク・"
         "Stale 0・欠けた行 0）。逆に、書き手が 2 つ以上なら、設定をどう工夫しても（locking を含めて）連鎖は止まらない。"),
        ("sec", "11-1  対策の一覧（優先順）"),
        ("table", ["優先", "対策", "効果", "手間", "注意"], [
            ["必須", "P1 トレースログの書き先をタスクごとに（-Diwin.log を mid/{タスクID} に。10 の案 A〜C）", "連鎖が起きなくなる", "小（起動スクリプト）", "フロントもバックも。デプロイは 00 分の前後を避ける"],
            ["必須", "P2 片付けは止まったタスクのディレクトリだけ（ECS の一覧と照合）", "動いているタスクのファイルを消さない", "小", "P1 でディレクトリが増えるのでセットで"],
            ["強く推奨", "P3 レイアウトに時刻・タスク・スレッドを入れる（PatternLayout）", "どのタスクの行か後から追える", "小（log4j2.xml）", "1 行が長くなる。容量を見積もる"],
            ["推奨", "P4 トレースログの正本を CloudWatch Logs に（サイドカー／FireLens／awslogs）", "EFS の事故・タスクの入れ替えと無関係にログが残る", "中", "料金（取り込み・保存）と保存期間を決める"],
            ["推奨", "P5 Failover の保険（A4 が書けないときは標準出力へ逃がす）", "ファイルに書けない間のログも残る", "小（log4j2.xml）", "A4 に ignoreExceptions=\"false\" が要る（Failover の決まり）"],
            ["推奨", "P6 監視（メトリクスフィルタ＋アラーム）", "起きたらすぐ気づく", "小", "Log4j2 の間引きがあるので「1 件以上」で鳴らす"],
            ["推奨", "P7 ヘルスチェックの設計（13）", "誤った一斉入れ替えを防ぎつつ、状態を見える化", "中（Spring MVC）", "根本対策の前に ELB を 503 にしない"],
            ["推奨", "P8 Log4j を 2.25.5 以降（または 2.26.1）へ", "2026 年の CVE への対応（本件とは無関係）", "小", "log4j-api／core／slf4j2-impl をそろえて上げる"],
            ["推奨", "P9 パスの命名規則（環境/サービス/コンテナ/タスク ID）を文書にし、レビューで確認", "同じ事故の再発防止", "小", "テスト環境も同じ規則に"],
        ], [3, 9, 6, 4.5, 6], ["c", "l", "l", "l", "l"]),
        ("sec", "11-2  起動スクリプトの例（案 A：-Diwin.log を mid/{タスクID} に）"),
        ("p", "JBoss のログ用に既にタスク ID を求めているなら、その値をそのまま使う。下は、ECS のタスクメタデータ（v4）からタスク ID を求める一般的な例。"),
        ("code", "entrypoint の一部（bash。UBI 9 の curl・sed・grep だけで動く）", [
            "#!/bin/bash",
            "set -eu",
            "BASE=/mnt/logs/front/logs/inter-api              # バックは /mnt/logs/back/logs/inter-api",
            "TASK_ID=\"\"",
            "if [ -n \"${ECS_CONTAINER_METADATA_URI_V4:-}\" ]; then",
            "  ARN=\"$(curl -fsS --max-time 2 \"${ECS_CONTAINER_METADATA_URI_V4}/task\" | grep -o '\"TaskARN\":\"[^\"]*\"' | head -n 1 | cut -d'\"' -f4)\" || ARN=\"\"",
            "  TASK_ID=\"${ARN##*/}\"",
            "fi",
            "[ -n \"${TASK_ID}\" ] || TASK_ID=\"$(uname -n)-$(date +%Y%m%d%H%M%S)\"   # 取れないときの予備（重ならない名前）",
            "LOGDIR=\"${BASE}/mid/${TASK_ID}\"                    # JBoss・GC・アクセスログと同じ場所",
            "mkdir -p \"${LOGDIR}\"",
            "# JBoss の起動コマンドに -D で渡す（standalone.sh は -D をシステムプロパティとして JVM に渡す）。",
            "# JAVA_OPTS を丸ごと export すると、standalone.conf の既定値（ヒープなど）が使われなくなるので注意。",
            "exec <EAP_HOME>/bin/standalone.sh -b 0.0.0.0 -Diwin.log=\"${LOGDIR}\" \"$@\"",
        ]),
        ("ul", [
            "-Diwin.log が standalone.xml の system-properties や standalone.conf で固定されていると、起動スクリプトの値が上書きされる。どこで決めているかを先に確かめる（08 の C-8）。",
            "ログのファイル名は今のまま（tracelog・trace.log.%d{yyyy-MM-dd-HH}）でよい。ディレクトリが分かれれば、ロールオーバは各タスクの中で 1 回だけになる。",
            "タスク ID のディレクトリは、タスクが止まった後も残る。片付け（11-5）とセットで入れる。",
        ]),
        ("sec", "11-3  log4j2.xml の例（タスクごと＋レイアウト＋Failover の保険）"),
        ("code", "案 C（${hostName}）とレイアウト・Failover をまとめた例。案 A なら fileName／filePattern は今のままでよい", [
            "<Configuration>",
            "  <Appenders>",
            "    <RollingFile name=\"A4\" ignoreExceptions=\"false\"",
            "                 fileName=\"${sys:iwin.log}/${hostName}/tracelog\"",
            "                 filePattern=\"${sys:iwin.log}/${hostName}/trace.log.%d{yyyy-MM-dd-HH}\">",
            "      <PatternLayout pattern=\"%d{yyyy-MM-dd HH:mm:ss.SSS} ${hostName} [%t] %m%n\"/>",
            "      <Policies><TimeBasedTriggeringPolicy/></Policies>",
            "    </RollingFile>",
            "    <Console name=\"TRACE_STDOUT\" target=\"SYSTEM_OUT\">",
            "      <PatternLayout pattern=\"TRACE-FAILOVER %d{yyyy-MM-dd HH:mm:ss.SSS} ${hostName} [%t] %m%n\"/>",
            "    </Console>",
            "    <Failover name=\"A4F\" primary=\"A4\" retryIntervalSeconds=\"60\">",
            "      <Failovers><AppenderRef ref=\"TRACE_STDOUT\"/></Failovers>",
            "    </Failover>",
            "  </Appenders>",
            "  <Loggers>",
            "    <Logger name=\"jp.iwin.base.tango.ILGLog4j.trace\" level=\"debug\" additivity=\"false\">",
            "      <AppenderRef ref=\"A4F\"/>",
            "    </Logger>",
            "  </Loggers>",
            "</Configuration>",
        ]),
        ("ul", [
            "Failover は「主のアペンダ（A4）が例外を投げたら、代わりのアペンダへ」という仕組み。そのため A4 に ignoreExceptions=\"false\" が要る（Log4j2 公式）。"
            "Failover 自身は既定で例外を外に出さないので、アプリ（Spring MVC）には届かない。",
            "代わりの先は標準出力。JBoss の設定によっては標準出力が server.log（[stdout]）にも入る。CloudWatch Logs に送っているなら、そこで拾える。",
            "retryIntervalSeconds（既定 60 秒）ごとに A4 を試し直す。Stale のままなら、次のロールオーバまで標準出力へ逃げ続ける。",
            "書き先を分けた後は Stale はほぼ起きないので、Failover は「もしもの保険」。監査でトレースログの欠けが許されない場合に入れる。",
        ]),
        ("sec", "11-4  ログの正本を CloudWatch Logs に"),
        ("table", ["方法", "しくみ", "よいところ", "気をつけるところ"], [
            ["サイドカー（CloudWatch Agent／Fluent Bit）", "同じタスクに収集用のコンテナを置き、自分のタスクの mid/{タスクID} のファイルを読んで送る",
             "今のファイル出力を変えずに足せる。タスクごとのログストリームにできる", "サイドカーにも同じタスク ID のディレクトリを教える（起動時に同じ方法で求める）"],
            ["FireLens（awsfirelens ログドライバ）", "アプリが標準出力に出したログを Fluent Bit が受けて送る", "ファイルを使わない（EFS と無関係）", "JBoss の標準出力の形（[stdout] の前置き）を整える必要がある"],
            ["awslogs ログドライバ", "コンテナの標準出力をそのまま CloudWatch Logs へ", "いちばん簡単", "標準出力に出すログの量・形を決める必要がある"],
        ], [5, 8, 6, 6], ["l", "l", "l", "l"]),
        ("p", "EFS は「ログを一時的に置く場所」、CloudWatch Logs は「正本」と役割を分けると、EFS の作り直し・片付けの事故でログを失わなくなる。"
              "既にサイドカーで JBoss のログを送っているなら、トレースログも同じ仕組みに乗せるのがいちばん早い。"),
        ("sec", "11-5  片付け（ハウスキーピング）のルール"),
        ("ul", [
            "消してよいのは「止まったタスク」のディレクトリ（mid/{タスクID}）だけ。動いているタスクの一覧（aws ecs list-tasks）と照合し、含まれるものは消さない。",
            "日数だけで消さない。動いているタスクでも、しばらく書かれないファイルはある。",
            "共有ディレクトリ（inter-api の直下）の古い trace.log.* は、全タスクが新しい書き先に移ったことを 08 の C-2 で確認してから移す。",
            "片付けの記録（いつ・何を・誰が）を残す。CloudTrail には EFS の中のファイル操作は残らない。",
        ]),
        ("code", "動いているタスクのディレクトリを除いて、7 日より古い mid/{タスクID} を一覧する（消す前に必ず目で確認）", [
            "RUNNING=$(aws ecs list-tasks --cluster <クラスタ> --service-name <サービス> --desired-status RUNNING --query 'taskArns[]' --output text | tr '\\t' '\\n' | sed 's#.*/##')",
            "find /mnt/logs/front/logs/inter-api/mid -mindepth 1 -maxdepth 1 -type d -mtime +7 | while read -r d; do",
            "  id=\"${d##*/}\"; echo \"${RUNNING}\" | grep -qx \"${id}\" && continue; echo \"消してよい候補: ${d}\"",
            "done",
        ]),
        ("sec", "11-6  監視（メトリクスフィルタとアラーム）"),
        ("code", "server.log を CloudWatch Logs に送っている場合（ロググループ名は環境に合わせる）", [
            "aws logs put-metric-filter --log-group-name <server.log のロググループ> --filter-name tracelog-write-error \\",
            "  --filter-pattern '?\"Stale file handle\" ?\"Unable to write to stream\" ?\"Unable to close stream\"' \\",
            "  --metric-transformations metricName=TraceLogWriteError,metricNamespace=App/Logging,metricValue=1,defaultValue=0",
            "aws cloudwatch put-metric-alarm --alarm-name tracelog-write-error --namespace App/Logging --metric-name TraceLogWriteError \\",
            "  --statistic Sum --period 300 --evaluation-periods 1 --threshold 1 --comparison-operator GreaterThanOrEqualToThreshold \\",
            "  --treat-missing-data notBreaching --alarm-actions <SNS トピックの ARN>",
        ]),
        ("p", "Log4j2 は同じアペンダのエラーを「最初の数件のあとは 5 分に 1 件」に間引くので、5 分の合計が 1 件以上で鳴らすのがちょうどよい。"
              "「Unable to close stream」は間引かれないので、毎時 00 分すぎに並べば共有ファイルの連鎖の目印になる。"),
        ("sec", "11-7  Log4j の版（2026 年 10 月時点）"),
        ("table", ["版", "公開日", "主な内容", "今回の設定への影響"], [
            ["2.25.3（今の版）", "2025-12-15", "Socket アペンダの TLS ホスト名確認の修正（CVE-2025-68161）", "—"],
            ["2.25.4", "2026-03-28", "CVE-2026-34477（<Ssl> の verifyHostName が無視される）・34478（Rfc5424Layout）・34480（XmlLayout）の修正",
             "RollingFile＋既定の PatternLayout だけなら当たらない見込み。他の設定ファイルも確認"],
            ["2.26.0", "2026-05-02", "機能の追加・整理", "—"],
            ["2.26.1／2.25.5", "2026-06-29／2026-07-01", "log4j-api の CVE-2026-49844（MapMessage.asJson の NaN・Infinity）の修正など", "JsonTemplateLayout などで MapMessage を使っていなければ当たらない見込み"],
        ], [4, 4, 10, 7], ["l", "c", "l", "l"]),
        ("p", "どの版にも、今回の「複数の JVM が同じファイルをロールオーバする」問題を直す変更は無い（Log4j2 は 1 つの JVM の中での調整しかしない設計）。"
              "版を上げても直らないので、P1 が先。"),
    ],
}

# ---------------------------------------------------------------------------
# 12 運用回避
# ---------------------------------------------------------------------------
CH12 = {
    "name": "12_運用回避", "no": "12", "title": "運用回避：やってはいけない操作・作り直しの手順・チェックリスト",
    "lead": "根本対策が入るまでの間、そして入った後も守る運用のルール。EFS の上では「動いているタスクの足元を動かさない」が合言葉。",
    "blocks": [
        ("sec", "12-1  やってはいけない操作"),
        ("table", ["操作", "何が起きるか", "代わりにどうするか"], [
            ["タスクが動いたまま EFS のファイルシステム・マウントターゲット・アクセスポイントを作り直す", "全タスクのマウント全体が Stale・応答なし（仮説 1）", "12-2 の手順で 0 タスクにしてから"],
            ["動いているタスクが使うディレクトリを rm -rf して作り直す", "そのディレクトリのファイルを開いていた全タスクが Stale", "作り直さない。起動スクリプトは mkdir -p だけ"],
            ["動いているタスクのファイルを手で消す・移す・上書きする", "そのタスクが Stale（または別のファイルに書く）", "止まったタスクのものだけを片付ける"],
            ["共有ファイルのまま、毎時 00 分の前後にデプロイ・スケールアウト", "新旧の書き手が増え、連鎖が長くなる", "05 分〜50 分の間に始めて終える"],
            ["同じ EFS・同じパスをテスト環境と本番で共用", "別環境のタスクが書き手になる", "環境ごとに EFS かアクセスポイント（rootDirectory）を分ける"],
            ["根本対策の前に、ヘルスチェックをトレースログの状態で 503 にする", "毎時 4〜5 タスクが不健康 → 一斉入れ替え", "13 の段階に沿って進める"],
        ], [8, 8, 8], ["l", "l", "l"]),
        ("sec", "12-2  EFS（やディレクトリ）を作り直すときの手順"),
        ("flow", [
            ("1", "影響範囲を決める", "そのファイルシステム（アクセスポイント）を使うサービス・タスク定義・環境をすべて洗い出す（ClientConnections も見る）。"),
            ("2", "書き手を止める", "対象サービスの desiredCount を 0 にし、タスクが 0 になったことを確かめる（デプロイ中のタスクにも注意）。"),
            ("3", "必要なログを退避する", "EFS 上のログを別の場所へコピーする（作り直すと消える）。"),
            ("4", "作り直す", "FS／マウントターゲット／アクセスポイントを作り直す。IaC なら plan の差分を確認してから。"),
            ("5", "タスク定義を合わせる", "新しい fileSystemId・accessPointId をタスク定義に入れ、新しいリビジョンにする（古い FS を指したままだと起動に失敗する）。"),
            ("6", "起動して確かめる", "desiredCount を戻し、各タスクで ls /mnt/logs・08 の C-2 を実行する。"),
        ]),
        ("sec", "12-3  根本対策が入るまでの約束（共有ファイルのままの間）"),
        ("ul", [
            "トレースログは毎時およそ 5/6 が失われている前提で、障害調査は JBoss の server.log・アクセスログ・アプリの別のログで補う。",
            "障害の時刻が分かっている場合は、その時間の CURRENT のタスク（08 の C-1・C-2 で特定）のログだけが残っている、と考える。",
            "デプロイ・スケールの時刻を毎時 05 分〜50 分に寄せる。",
            "トレースログの欠けを、監査・報告の窓口に早めに知らせる。",
        ]),
        ("sec", "12-4  チェックリスト（変更の前後で確認する）"),
        ("table", ["済", "確認すること", "どうやって"], [
            ["", "フロント・バックとも、tracelog の書き先がタスクごとに分かれている", "08 の C-8（-Diwin.log・リンク先）"],
            ["", "全タスクで tracelog-fd-check.sh が CURRENT", "08 の C-2（毎時 02 分以降）"],
            ["", "server.log に Stale file handle・Unable to close stream が出ていない（2〜3 時間）", "08 の C-1・11-6 のアラーム"],
            ["", "ls /mnt/logs と mid/{タスクID} の更新が正常", "08 の C-5・C-6"],
            ["", "片付けは止まったタスクのディレクトリだけを対象にしている", "11-5"],
            ["", "EFS を共用している別環境・別サービスが無い（ClientConnections が想定どおり）", "08 の C-9"],
            ["", "ELB のヘルスチェックはリクエストの処理能力だけを見ている（503 の条件を決めた）", "13"],
            ["", "Log4j を 2.25.5 以降（2.26.1）にした、または計画に入れた", "11-7"],
        ], [2, 13, 7], ["c", "l", "l"], {"check": True}),
        ("p", "「済」の欄は ○（済）／×（未）／－（対象外）から選ぶ。"),
    ],
}

# ---------------------------------------------------------------------------
# 13 ヘルスチェック（Spring MVC）
# ---------------------------------------------------------------------------
CH13 = {
    "name": "13_ヘルスチェック", "no": "13", "title": "ヘルスチェック：Spring MVC の API が 200 を返す理由と、安全な設計",
    "lead": ("結論：200 は Controller の握りつぶしではなく、Log4j2 が例外をアプリに渡さない設計（ignoreExceptions=true）の結果。"
             "ヘルスチェックで気づきたいなら、例外を待たずに「トレースログの状態を自分で調べる」必要がある。ただし今の構成のまま ELB を 503 にしてはいけない。"),
    "blocks": [
        ("sec", "13-1  いまのヘルスチェックでわかること・わからないこと"),
        ("table", ["項目", "わかるか", "理由"], [
            ["JBoss が動き、Spring MVC の DispatcherServlet が応答できる", "わかる", "HTTP で 200 が返ってくること自体が証拠"],
            ["業務の処理（DB など）ができる", "API が調べていれば", "調べていなければわからない（今は常に 200）"],
            ["トレースログが書けている", "わからない", "Log4j2 は書けなくても例外をアプリに渡さない。API も調べていない"],
            ["EFS のマウントが生きている", "ほぼわからない", "API がファイルに触れなければ、マウントが止まっていても 200（触れると応答が止まり、タイムアウトで失敗に見える）"],
        ], [8, 4, 12], ["l", "c", "l"]),
        ("sec", "13-2  200 が返る理由：3 つの可能性の見分け"),
        ("table", ["可能性", "あてはまるか", "根拠・確かめ方"], [
            ["① Log4j2 が例外を受け止めているので、Controller に届いていない（設計どおり）",
             "あてはまる（今回の主な理由）",
             "A4 の ignoreExceptions は既定の true。AppenderControl.java 168〜173 行で処理が終わり、log4j-api の AbstractLogger.java 2962〜2988 行も呼び出し元へ投げない。"
             "再現実験でもアプリは 1 件も例外を受け取らずに動き続けた"],
            ["② Controller・@ControllerAdvice・Filter が例外を握りつぶして 200 にしている（実装ミス）",
             "今回の Stale については、あっても関係しない（届く例外が無い）。別の異常を隠していないかは確認する価値あり",
             "13-4 の観点でコードを見る（catch (Exception) で 200、@ExceptionHandler(Exception.class) で 200 など）"],
            ["③ ヘルスチェックが何も調べていない（常に 200 を返す作り）",
             "あてはまる（①と組み合わさって 200 になる）",
             "「Stale を検知できない」のは、検知する処理が無いため。設計上の不足であって、例外処理のミスではない"],
        ], [8, 6, 10], ["l", "l", "l"]),
        ("callout", "「意図的に catch してスローし直さないと検知できないのか」への答え",
         "catch しようにも、例外は Controller まで来ない。Spring MVC 側で何を書いても、既定の Log4j2 からは何も受け取れない。"
         "ignoreExceptions=\"false\" にすれば AppenderLoggingException が logger.debug() から飛んでくるが、それは「ログを書いた業務のリクエスト」が失敗するだけで、"
         "ヘルスチェック API には届かない（ヘルスチェック API がトレースログを書かない限り）。ヘルスチェックで見たいなら、ヘルスチェック自身が状態を調べる。"),
        ("sec", "13-3  Spring MVC で、例外が HTTP の状態になるまで"),
        ("flow", [
            ("1", "Controller のメソッドが例外を投げる", "例：業務処理の中で RuntimeException。Log4j2 の Stale は（既定では）ここまで来ない。"),
            ("2", "DispatcherServlet が HandlerExceptionResolver に順に聞く",
             "@ExceptionHandler（@ControllerAdvice を含む）→ @ResponseStatus・ResponseStatusException → Spring MVC の標準の例外（405・415 など）の順。"),
            ("3", "どれも処理しなければ、サーブレットコンテナへ",
             "例外は DispatcherServlet から外へ出て、JBoss（Undertow）が 500 のエラーページを返す。Spring MVC の既定では 503 にはならない。"),
            ("4", "503 にしたいとき",
             "ResponseEntity.status(HttpStatus.SERVICE_UNAVAILABLE)、throw new ResponseStatusException(HttpStatus.SERVICE_UNAVAILABLE)、"
             "例外クラスに @ResponseStatus(HttpStatus.SERVICE_UNAVAILABLE)、@ExceptionHandler で 503 を返す、のどれかで明示する。"
             "（Spring Boot Actuator の health は、DOWN を 503 にする既定を持つ。Boot を使っていなければ自分で決める）"),
        ]),
        ("sec", "13-4  握りつぶしがないか、コードで確かめる観点"),
        ("table", ["見る場所", "握りつぶしの例", "なぜ問題か"], [
            ["ヘルスチェックの Controller", "try { … } catch (Exception e) { return ResponseEntity.ok(\"OK\"); }", "調べた結果の異常まで 200 にしてしまう"],
            ["@ControllerAdvice／@ExceptionHandler", "@ExceptionHandler(Exception.class) で 200 と本文だけを返す", "すべての API の失敗が 200 に見える（ELB も監視も気づけない）"],
            ["自作の HandlerExceptionResolver", "response.setStatus(200) にしてしまう", "同上"],
            ["Servlet Filter（OncePerRequestFilter など）", "chain.doFilter を catch で包み、例外を飲み込む", "Spring MVC の外で消えるので気づきにくい"],
            ["web.xml の error-page と、その先のページ", "エラーページを返す Controller が 200 で返す", "500 のはずが 200 に変わる"],
            ["ログ呼び出しの周り", "try { log.debug(…) } catch (Exception e) { }", "既定の Log4j2 では投げられないので今は無害。ignoreExceptions=\"false\" にしたときに効いてくる"],
        ], [6, 9, 9], ["l", "l", "l"]),
        ("sec", "13-5  なぜ今の構成のまま 503 にしてはいけないのか"),
        ("seq", ["時刻", "タスク（6 つ）", "ELB（30 秒ごと・2 回失敗で外す・5 回成功で戻す）", "ECS サービス"], [
            ("x", ["13:00:01", "連鎖で 5 タスクが STALE。ヘルスチェックが 503 を返し始める", "", ""]),
            ("x", ["13:00:30〜13:01:00", "", "2 回続けて失敗した 5 タスクを外す。1 タスクに全リクエストが集まる", ""]),
            ("x", ["13:01〜13:03", "残った 1 タスクが過負荷になる", "（全部が不健康なら、全部に振り分ける fail-open）", "ELB で不健康なタスクを止め、新しいタスクを起動"]),
            ("", ["13:03〜13:06", "新しいタスクは今の tracelog を開く → CURRENT に見える", "新しいタスクは最初のヘルスチェック 1 回の成功で振り分けに入る（外したタスクが戻るには 5 回連続の成功＝約 2.5 分）", ""]),
            ("x", ["14:00:01", "また連鎖。新しいタスクも含めて 5 タスクが STALE", "また外す", "また入れ替える（毎時くり返す）"]),
        ], [3, 8, 8, 6]),
        ("p", "入れ替えても共有ファイルは変わらないので、毎時同じことがくり返され、そのたびに処理能力が落ちる。だから順番は「根本対策 → 監視 → 必要ならヘルスチェックに含める」。"),
        ("sec", "13-6  安全な設計（段階）"),
        ("table", ["段階", "ELB のヘルスチェック", "トレースログの見方", "条件"], [
            ["0（今すぐ）", "そのまま（200）。リクエストを処理できるかだけを見る", "server.log のメトリクスフィルタ＋アラーム（11-6）", "—"],
            ["1（根本対策と同時）", "そのまま", "トレースログの状態を返す専用の API（/health/tracelog）を追加し、監視・ECS Exec で見る", "13-7 の実装例"],
            ["2（根本対策の後・必要なら）", "STALE が数分続いたら 503 にする、などゆとりを持たせて含めるかを判断", "専用の API の結果を使う", "1 ファイル 1 書き手になっていること。全タスク同時の失敗は fail-open になる点も考える"],
        ], [4, 7, 8, 6], ["l", "l", "l", "l"]),
        ("sec", "13-7  Spring MVC の実装例：トレースログの状態を調べる API"),
        ("p", "例外を待つのではなく、Java のプロセスが開いているファイル（/proc/self/fd）を自分で調べる。tools/tracelog-fd-check.sh と同じ考え方。"
              "Linux（Fargate）専用。EAP 8.1 の Spring MVC（jakarta.*）を想定。"),
        ("code", "TraceLogProbe.java（状態を調べる部品）", [
            "import java.io.IOException;",
            "import java.nio.file.*;",
            "",
            "/** -Diwin.log のディレクトリ直下で、このプロセスが開いているトレースログの状態を返す */",
            "public final class TraceLogProbe {",
            "    public enum State { CURRENT, NOT_CURRENT, STALE, NOFD, MOUNTSTALE, ERROR }",
            "",
            "    public static State check() {",
            "        Path dir = Paths.get(System.getProperty(\"iwin.log\", \"/webapp/webapp9mf02/logs\"));",
            "        try {",
            "            Path real = dir.toRealPath();                                   // リンクをたどる",
            "            Object cur = Files.getAttribute(real.resolve(\"tracelog\"), \"unix:ino\");",
            "            try (DirectoryStream<Path> fds = Files.newDirectoryStream(Paths.get(\"/proc/self/fd\"))) {",
            "                for (Path fd : fds) {",
            "                    Path target;",
            "                    try { target = Files.readSymbolicLink(fd); } catch (IOException e) { continue; }",
            "                    Path p = Paths.get(target.toString().replace(\" (deleted)\", \"\"));",
            "                    if (!real.equals(p.getParent())) continue;                // そのディレクトリの直下だけ",
            "                    String n = p.getFileName().toString();                   // トレースログだけ（server.log などは数えない）",
            "                    if (!n.equals(\"tracelog\") && !n.startsWith(\"trace.log.\")) continue;",
            "                    try {",
            "                        Object ino = Files.getAttribute(fd, \"unix:ino\");       // リンクをたどって stat → EFS に問い合わせ",
            "                        return ino.equals(cur) ? State.CURRENT : State.NOT_CURRENT;",
            "                    } catch (FileSystemException e) {",
            "                        return String.valueOf(e.getReason()).contains(\"Stale file handle\") ? State.STALE : State.ERROR;",
            "                    }",
            "                }",
            "            }",
            "            return State.NOFD;",
            "        } catch (IOException e) {",
            "            return String.valueOf(e.getMessage()).contains(\"Stale file handle\") ? State.MOUNTSTALE : State.ERROR;",
            "        }",
            "    }",
            "}",
        ]),
        ("code", "TraceLogHealthController.java（専用の API。段階 1 では監視からだけ呼ぶ）", [
            "import org.springframework.http.HttpStatus;",
            "import org.springframework.http.ResponseEntity;",
            "import org.springframework.web.bind.annotation.GetMapping;",
            "import org.springframework.web.bind.annotation.RestController;",
            "",
            "@RestController",
            "public class TraceLogHealthController {",
            "    @GetMapping(\"/health/tracelog\")",
            "    public ResponseEntity<String> tracelog() {",
            "        TraceLogProbe.State s = TraceLogProbe.check();",
            "        HttpStatus st = (s == TraceLogProbe.State.CURRENT) ? HttpStatus.OK : HttpStatus.SERVICE_UNAVAILABLE;",
            "        return ResponseEntity.status(st).body(\"tracelog=\" + s);     // 例外ではなく、調べた結果で 503 を返す",
            "    }",
            "}",
        ]),
        ("ul", [
            "ELB のヘルスチェックのパス（今の API）は変えずに、まずはこの API を監視（外形監視・定期ジョブ・ECS Exec）から呼ぶ。",
            "ロールオーバの直後（毎時 00 分すぎの 1 分ほど）は、NFS の名前のキャッシュで NOT_CURRENT を CURRENT と見ることがある。STALE は EFS の返事そのものなので確か。",
            "1 回の呼び出しで EFS への問い合わせは数回（stat）。30 秒ごとでも負担は小さい。ただし EFS が応答しないときに固まらないよう、監視側でタイムアウトを短く。",
            "別の方法として、A4 に自作の ErrorHandler を付けて最後の失敗時刻を覚えさせ、API で返すこともできる（Log4j2 の内部に依存するので、上の方法のほうが単純）。",
        ]),
        ("sec", "13-8  ECS のコンテナヘルスチェックとの違い"),
        ("table", ["", "ELB（ALB）のヘルスチェック", "ECS のコンテナヘルスチェック"], [
            ["だれが確かめる", "ロードバランサがネットワーク越しに HTTP で", "コンテナの中でコマンドを実行（終了コード 0 が成功）"],
            ["既定の間隔など", "30 秒・タイムアウト 5 秒・2 回失敗で外す・5 回成功で戻す・成功コード 200", "タスク定義で決める（interval・timeout・retries・startPeriod）"],
            ["失敗すると", "振り分けから外す。ECS サービスは不健康と報告されたタスクを入れ替える", "必須（essential）コンテナが UNHEALTHY ならタスクが UNHEALTHY → サービスが入れ替える"],
            ["今回の使い方", "リクエストを処理できるかだけを見る", "トレースログの状態は入れない（13-5 の理由）"],
        ], [4, 10, 10], ["l", "l", "l"]),
    ],
}

# ---------------------------------------------------------------------------
# 14 コマンド集
# ---------------------------------------------------------------------------
CH14 = {
    "name": "14_コマンド集", "no": "14", "title": "コマンド集：調査・確認に使うものを 1 か所に",
    "lead": "<クラスタ>・<サービス>・<コンテナ> は環境に合わせる。読むだけのコマンドから順に並べた。ECS Exec には Session Manager プラグインが要る。",
    "blocks": [
        ("sec", "14-1  タスクの一覧と ECS Exec"),
        ("code", "bash（CloudShell・Linux・Mac）", [
            "aws ecs list-tasks --cluster <クラスタ> --service-name <サービス> --desired-status RUNNING --query 'taskArns[]' --output text",
            "aws ecs execute-command --cluster <クラスタ> --task <タスクID> --container <フロントのコンテナ名> --interactive --command \"/bin/bash\"",
        ]),
        ("code", "PowerShell（Windows）", [
            "$Cluster = \"<クラスタ>\"; $Service = \"<サービス>\"; $Container = \"<フロントのコンテナ名>\"",
            "$tasks = (aws ecs list-tasks --cluster $Cluster --service-name $Service --desired-status RUNNING --query \"taskArns[]\" --output text) -split \"\\s+\" | Where-Object { $_ }",
            "foreach ($t in $tasks) { Write-Host \"=== $($t.Split('/')[-1])\"; aws ecs execute-command --cluster $Cluster --task $t --container $Container --interactive --command \"/bin/bash\" }",
        ]),
        ("sec", "14-2  コンテナの中で：トレースログの判定（ツールが無いときの短縮版）"),
        ("code", "貼り付けて実行（CURRENT・STALE・OTHER を表示。OTHER は ls -i で名前を確かめる）", [
            "export LC_ALL=C",
            "PID=$(for p in /proc/[0-9]*; do [ \"$(readlink $p/exe 2>/dev/null | sed 's#.*/##')\" = java ] && echo ${p#/proc/}; done | head -1)",
            "D=$(readlink -f \"$(tr '\\0' '\\n' < /proc/$PID/cmdline | sed -n 's/^-Diwin\\.log=//p' | head -1)\"); [ -n \"$D\" ] || D=$(readlink -f /webapp/webapp9mf02/logs)",
            "C=$(stat -c %i \"$D/tracelog\")",
            "for f in /proc/$PID/fd/*; do t=$(readlink $f); t=${t% (deleted)}; [ \"$(dirname \"$t\")\" = \"$D\" ] || continue; case \"${t##*/}\" in tracelog|trace.log.*) ;; *) continue;; esac;",
            "  i=$(stat -L -c %i $f 2>&1); case \"$i\" in *Stale*) echo \"STALE fd=${f##*/}\";; \"$C\") echo \"CURRENT fd=${f##*/}\";; *) echo \"OTHER fd=${f##*/} inode=$i\";; esac; done",
            "ls -li --time-style=full-iso \"$D\" | grep -E 'tracelog|trace[.]log[.]'",
        ]),
        ("sec", "14-3  コンテナの中で：マウント・設定・JBoss のログ"),
        ("code", "", [
            "ls /mnt/logs >/dev/null && echo MOUNT_OK",
            "grep ' /mnt/logs ' /proc/mounts",
            "readlink -f /webapp/webapp9mf02/logs /webapp/webapp9mb02/logs 2>/dev/null",
            "tr '\\0' '\\n' < /proc/$PID/cmdline | grep -E 'iwin.log|jboss.server.log.dir|Xlog:gc|log4j'",
            "ls -l --time-style=full-iso /mnt/logs/front/logs/inter-api/mid/ | tail -n 8",
            "grep -n -E 'Stale file handle|Unable to write to stream|Unable to close stream' <server.log のパス> | tail -n 20",
        ]),
        ("sec", "14-4  CloudWatch Logs Insights（server.log を送っている場合）"),
        ("code", "時間ごと・ログストリーム（タスク）ごとのエラーの数", [
            "fields @timestamp, @logStream, @message",
            "| filter @message like /Stale file handle|Unable to write to stream|Unable to close stream/",
            "| stats count(*) as n by @logStream, bin(1h)",
            "| sort bin(1h) desc",
        ]),
        ("code", "毎時 00 分すぎに「Unable to close stream」が並ぶか（連鎖の目印）", [
            "fields @timestamp, @logStream",
            "| filter @message like /Unable to close stream/",
            "| stats count(*) as n, min(@timestamp) as first by bin(1h)",
        ]),
        ("sec", "14-5  AWS の記録"),
        ("code", "CloudTrail（EFS の作成・削除）・ECS（デプロイの履歴）・EFS の接続数", [
            "aws cloudtrail lookup-events --lookup-attributes AttributeKey=EventSource,AttributeValue=elasticfilesystem.amazonaws.com \\",
            "  --start-time 2026-10-01T00:00:00Z --query 'Events[].[EventTime,EventName,Username]' --output table",
            "aws ecs describe-services --cluster <クラスタ> --services <サービス> --query 'services[0].deployments[].[createdAt,status,taskDefinition,runningCount]' --output table",
            "aws ecs describe-services --cluster <クラスタ> --services <サービス> --query 'services[0].events[0:30].[createdAt,message]' --output table",
            "aws cloudwatch get-metric-statistics --namespace AWS/EFS --metric-name ClientConnections --dimensions Name=FileSystemId,Value=<fs-ID> \\",
            "  --statistics Sum --period 60 --start-time 2026-10-10T03:00:00Z --end-time 2026-10-10T04:00:00Z",
        ]),
        ("sec", "14-6  ELB のヘルスチェックの状態"),
        ("code", "", [
            "aws elbv2 describe-target-health --target-group-arn <ターゲットグループの ARN> --query 'TargetHealthDescriptions[].[Target.Id,TargetHealth.State,TargetHealth.Reason]' --output table",
            "aws elbv2 describe-target-groups --target-group-arns <ターゲットグループの ARN> --query 'TargetGroups[0].[HealthCheckPath,HealthCheckIntervalSeconds,HealthCheckTimeoutSeconds,HealthyThresholdCount,UnhealthyThresholdCount,Matcher.HttpCode]'",
        ]),
        ("sec", "14-7  再現実験（このフォルダの lab/）"),
        ("code", "Docker（--privileged が使えること）があれば、約 20 分で 4 ケースを再現する", [
            "bash lab/run_lab6.sh              # C1〜C4 すべて",
            "bash lab/run_lab6.sh C1 C3        # 指定ケースだけ",
            "python -X utf8 lab/analyze.py lab/results/C1   # 集計（analysis.md・analysis.json）",
            "python -X utf8 build/build_docs.py             # この資料（Excel・Markdown）を作り直す",
        ]),
    ],
}


# ---------------------------------------------------------------------------
# 15 検証結果
# ---------------------------------------------------------------------------
def _runs():
    """[(回, ラベル, C1 の結果)]（3 回目が本番と同じ配置）"""
    out = []
    for run, label in ((1, "1 回目（旧い配置）"), (2, "2 回目（旧い配置・ツール改良）"), (3, "3 回目（本番と同じ配置）")):
        r = L.load("C1", run=run)
        if r:
            out.append((run, label, r))
    return out


def _boundary_table():
    rows = []
    for run, label, r in _runs():
        for b in L.boundary_rows(r):
            rows.append([label, b["b"], " → ".join(b["order"]), str(b["n_cur"]), str(b["n_arc"]), str(b["n_stale"]),
                         "、".join(b["cur"]) or "-", "一致" if b["cur"] == [b["last"]] else ("一致（2 つ）" if b["last"] in b["cur"] else "不一致")])
    return rows or [["（未実施）", "", "", "", "", "", "", ""]]


def _case_summary():
    rows = []
    c1, c2, c3, c4 = L.load("C1"), L.load("C2"), L.load("C3"), L.load("C4")

    def tot(r):
        t = L.totals(r)
        return "書いた %d 行／正しい %s／別の時間帯 %s／消えた %s" % (t["emitted"], t["ok_p"], t["mis_p"], t["lost_p"])

    if c1:
        se, sf = L.server_log(c1)
        rows.append(["C1", "いまの構成（6 タスクが同じ tracelog）・NFSv3（EFS と同じく消された実体に Stale を返す）",
                     tot(c1) + "。server.log（mid/{タスク}）は %d/%d 行残った" % (sf, se),
                     "毎分、正しく書けたのは 1 タスク。IOException: Stale file handle を再現。タスクごとの server.log は無事"])
    if c2:
        se, sf = L.server_log(c2)
        a2, n2 = L.tool_accuracy(c2)
        rows.append(["C2", "いまの構成・NFSv4.1（Linux の knfsd：消されても実体を残すサーバ）",
                     tot(c2) + "。Log4j2 のエラー表示 %d 件。診断ツールの判定はサーバ側と %d/%d 一致" % (L.stale_shown(c2), a2, n2),
                     "エラーが 1 件も出なくても行は消える。サーバの作りで「エラーの有無」が変わるだけで、原因は同じ。ツール（stat）は STALE を見つけられる"])
    if c3:
        se, sf = L.server_log(c3)
        rows.append(["C3", "恒久対策（-Diwin.log を mid/{タスク} に。Log4j2 の設定は同じ）・NFSv3",
                     tot(c3) + "。Stale の表示 %d 件" % L.stale_shown(c3),
                     "1 ファイル 1 書き手にすると、EFS と同じ厳しいサーバでも全部残る"])
    if c4:
        p = c4.get("post_recreate") or {}
        rows.append(["C4", "仮説 1（動いている最中に FS を作り直す：中身を消し、同じ IP・別の fsid で出し直す）・NFSv3",
                     "作り直しの後：トレース %d 行中 %d 行、server.log %d 行中 %d 行が残った。全タスクで ls /mnt/logs が Stale" % (
                         p.get("trace_emitted", 0), p.get("trace_found", 0), p.get("server_emitted", 0), p.get("server_found", 0)),
                     "マウント全体が壊れ、タスクごとの server.log も書けない。今回の観察（JBoss のログは無事）と合わない"])
    return rows or [["（未実施）", "", "", ""]]


def _task_table(r):
    if not r:
        return [["（未実施）", "", "", "", "", "", "", ""]]
    rows = []
    for t in r["tasks"]:
        p = r["per_task"][t]
        e = r["stderr"][t]
        s = r["server_log"][t]
        rows.append([t, str(p.get("emitted", 0)), str(p.get("ok", 0)), str(p.get("misplaced", 0)), str(p.get("lost", 0)),
                     str(e.get("write_err_trace", 0)), str(e.get("close_err", 0)), "%d/%d" % (s["found"], s["expected"])])
    return rows


def _file_table(r):
    if not r:
        return [["（未実施）", "", "", ""]]
    rows = []
    for f, v in r["files"].items():
        tasks = "、".join("%s %d 行" % (k, n) for k, n in sorted(v["tasks"].items(), key=lambda x: int(x[0][1:])))
        mins = "、".join("%s %d 行" % (k[-5:].replace("-", ":"), n) for k, n in sorted(v["minutes"].items()))
        rows.append([f, tasks, mins, "NUL %d／壊れた行 %d" % (v["nul"], v["broken"])])
    return rows


def _tool_rows():
    rows = []
    for label, r in (("C1 3 回目", L.load("C1")), ("C1 2 回目", L.load("C1", run=2)), ("C2", L.load("C2")), ("C3", L.load("C3")),
                     ("C4（作り直しの前後）", L.load("C4"))):
        if not r:
            continue
        a, n = L.tool_accuracy(r)
        miss = []
        for s in r["snapshots"]:
            for k, v in s.get("verdicts", {}).items():
                tv = s.get("truth", {}).get(k)
                if tv and v != tv:
                    miss.append("%s：ツール %s／実際 %s（%s）" % (k, v, tv, s["file"]))
        rows.append([label, "%d/%d" % (a, n), "；".join(miss) or "なし"])
    return rows or [["（未実施）", "", ""]]


def _meta_rows():
    m = L.meta()
    return [
        ["日時（日本時間）", "2026-10-10。1 回目 17:04〜、2 回目 18:35〜（どちらも旧い配置）、3 回目 18:49〜（本番と同じ配置。C3 だけ 19:08 に診断ツールを直して取り直し）"],
        ["Docker・カーネル", m.get("docker", "-")],
        ["クライアント（タスクの代わり）", m.get("client", "-")],
        ["サーバ（EFS の代わり）", m.get("server", "-")],
        ["タスク数・書く間隔", "6 タスク。各タスクが 100〜400 ミリ秒ごとに 1 行（リクエストの代わり）"],
        ["Log4j2 の設定", "A4 はユーザーの設定そのまま（RollingFile・TimeBasedTriggeringPolicy・レイアウトなし）。filePattern の最小単位だけ「時」→「分」"],
        ["配置", "/webapp/webapp9mf02/logs → /mnt/logs/front/logs/inter-api（共有）。server.log は /mnt/logs/front/logs/inter-api/mid/T1〜T6（タスクごと）"],
        ["数え方", "各タスクが「何番の行をいつ書いたか」を自分のディスクに記録し、NFS サーバに残った行と突き合わせる（正しい／別の時間帯／消えた）"],
    ]


_C1 = L.load("C1")

CH15 = {
    "name": "15_検証結果", "no": "15", "title": "検証結果：Docker で 6 タスク＋NFS を立てて再現した（Log4j 2.25.3）",
    "lead": ("EFS の代わりに Linux の NFS サーバ（knfsd）、ECS タスクの代わりに UBI 9.8＋OpenJDK 21＋Log4j 2.25.3 のコンテナ 6 台。"
             "ロールオーバの周期だけ 1 時間 → 1 分に縮めた。3 回目は本番と同じディレクトリ配置で行い、本文の数字はこれを使った。"),
    "blocks": [
        ("sec", "15-1  環境"),
        ("table", ["項目", "内容"], _meta_rows(), [6, 18], ["l", "l"]),
        ("sec", "15-2  ケースと結果の一覧"),
        ("table", ["ケース", "条件", "結果", "わかったこと"], _case_summary(), [2, 8, 9, 8], ["c", "l", "l", "l"]),
        ("sec", "15-3  「1 タスクだけ正常」の確認（境目ごとの実際の状態。行の行き先から判定）"),
        ("table", ["回", "境目（UTC）", "ロールオーバの順番（左が先）", "CURRENT", "ARCHIVE", "STALE", "正しく書けたタスク", "最後のタスクと"],
         _boundary_table(), [4, 3, 7, 2, 2, 2, 3, 3], ["l", "c", "l", "c", "c", "c", "c", "c"]),
        ("p", "どの回・どの境目でも、正しく書けたのは「その分の最後にロールオーバしたタスク」だった。1・2 回目は、デプロイ直後の最初の境目だけ ARCHIVE が 1 つ出た"
              "（05 の型 A が 1 回混ざる）。3 回目は最初から型 B だけだった。"),
        ("sec", "15-4  C1 のタスクごとの数字（3 回目）"),
        ("table", ["タスク", "書いた", "正しい", "別の時間帯", "消えた", "書き込み失敗の表示", "閉じる失敗の表示", "server.log 残り/期待"],
         _task_table(_C1), [2, 2, 2, 3, 2, 4, 4, 4], ["c", "c", "c", "c", "c", "c", "c", "c"]),
        ("ul", [
            "「書き込み失敗の表示」は標準エラーに出た Unable to write to stream の数。数百行が消えたタスクでも 2 件ほど（DefaultErrorHandler の間引き）。",
            "「閉じる失敗の表示」は毎分のロールオーバで出た Unable to close stream: Stale file handle の数（間引かれない）。毎時 00 分すぎに並ぶ目印になる。",
            "server.log（共有ディレクトリの下の mid/{タスク}）は、同じマウント・同じ親ディレクトリでも 1 行も欠けなかった。",
            "Java のアプリは 1 件も例外を受け取らずに最後まで動いた（Log4j2 が受け止めている）。",
        ]),
        ("sec", "15-5  C1 で各ファイルに残った行（3 回目）"),
        ("table", ["ファイル", "どのタスクの行か", "どの分（UTC）の行か", "壊れ"], _file_table(_C1), [6, 6, 7, 4], ["l", "l", "l", "l"]),
        ("p", "保存ファイル（trace.log.*）には、どれも 1 タスク分の行しか残らない。最初の分のファイル（ロールオーバの前に 6 タスクが同じ実体へ追記していた分）も 1 タスク分だけで、"
              "これは交換ではなく NFS の追記どうしの上書きによる（04 の 4-8）。名前と中身の分が 1 つずれているファイルがあれば、型 A（上書き）で ARCHIVE のタスクが書いたもの。"),
        ("sec", "15-6  診断ツール（tools/tracelog-fd-check.sh）の正確さ"),
        ("table", ["ケース", "サーバ側の実体と一致", "ずれた判定"], _tool_rows(), [4, 4, 16], ["l", "c", "l"]),
        ("p", "ずれたのは、どれもロールオーバから 30 秒以内（25 秒後）のスナップショットで、ARCHIVE を CURRENT と見たもの（NFS クライアントの名前のキャッシュ）。"
              "ツールはこのとき「# 注意: … 秒前に変わったばかり」と出す。毎時 02 分以降に実行すれば避けられる。STALE の判定は一度もずれなかった。"),
        ("sec", "15-7  わかったこと（まとめ）"),
        ("ul", [
            "6 タスクが同じ tracelog を使うと、毎分（本番では毎時）の境目のあと、正しく書けるのは最後にロールオーバした 1 タスクだけ。",
            "消えた行は全体の約 8 割。残るのは 1 タスク分（約 1/6）だけで、型 A が起きると名前の時間がずれる。",
            "ロールオーバの前（全タスクが同じ実体に追記している間）も、NFS の追記の上書きで、残るのはほぼ 1 タスク分だった。エラーは出ない。",
            "タスクごとのディレクトリ（mid/{タスク}）のログは、同じマウント・同じ親ディレクトリでも無事。違いは書き手の数だけ。",
            "書き先をタスクごとに分ける（-Diwin.log を mid/{タスク} に）だけで、Stale 0・欠け 0 になった。Log4j2 の設定は変えていない。",
            "FS の作り直し（仮説 1）は、マウント全体と全タスクのすべてのログを壊す。今回の観察とは見え方がはっきり違う。",
            "knfsd（NFSv4.1）ではエラーが出ないまま行が消える。エラーが出るかどうかはサーバ次第で、原因（共有ファイル）は同じ。"
            "このときも診断ツールは STALE を見つけた（stat はサーバに問い合わせるため）。「エラーが無い＝正常」とは言えない。",
        ]),
        ("sec", "15-8  この検証の限界"),
        ("ul", [
            "サーバは EFS ではなく Linux の knfsd。EFS が「別のクライアントに消された実体に STALE を返す」ことは、EFS 側の技術者の LKML 投稿（2020）と、"
            "今回の本番の例外そのもので裏付けた。実験ではその振る舞いを NFSv3 で再現した。",
            "Fargate のカーネルや EFS のキャッシュの細かな振る舞いは、Docker Desktop（WSL2 のカーネル 5.15）と同じではない。型 A／型 B の割合は環境とリクエストの間隔で変わる。",
            "ロールオーバの周期を 1 分に縮めた。仕組み（filePattern の最小単位が変わった後の最初のログで交換）は 1 時間でも同じ。",
            "JBoss・Spring MVC は使っていない（Log4j2 を直接呼ぶ小さな Java プログラム）。Log4j2 の中の動きは同じ。",
        ]),
    ],
}

# ---------------------------------------------------------------------------
# 16 用語集
# ---------------------------------------------------------------------------
CH16 = {
    "name": "16_用語集", "no": "16", "title": "用語集（小学生向けのたとえつき）",
    "lead": "むずかしい言葉を、たとえと一緒に。",
    "blocks": [
        ("table", ["用語", "意味", "たとえ"], [
            ["ファイル", "名前のついたデータのかたまり", "ノート"],
            ["ディレクトリ", "ファイルを入れる入れ物（フォルダ）", "たなの段・引き出し"],
            ["inode（実体）", "ファイルの中身そのものと、その番号", "ノートそのもの（表紙の名前ではなく）"],
            ["ファイル名", "ディレクトリの中の見出し。付け替えられる", "ノートの表紙のラベル"],
            ["FD（ファイル記述子）", "プログラムが開いたファイルを指す番号", "手元の番号札"],
            ["ファイルハンドル", "NFS でサーバが発行する、実体を指す引換券", "クロークの番号札"],
            ["ESTALE／Stale file handle", "引換券の品物が、もうサーバに無いというエラー（116）", "「その番号のノートはもうありません」"],
            ["シンボリックリンク", "別の場所を指す道しるべのファイル", "「ノートは職員室のたなにあります」という貼り紙"],
            ["NFS", "ネットワークの向こうのディスクを手元のように使う仕組み", "みんなで使う職員室のたな"],
            ["EFS", "AWS の NFS（みんなで使えるファイル置き場）", "学校全体の共用たな"],
            ["NFS クライアント", "NFS を使う側（各タスクのカーネル）", "たなを使いに来る人"],
            ["close-to-open", "閉じたら書き戻し、開くときに確かめる、という約束", "ノートを返すときに書き終え、借りるときに最新を確かめる"],
            ["O_APPEND（追記）", "ファイルの最後に書き足す開き方。NFS では同時の追記は保証されない", "ノートの最後のページに書き足す"],
            ["ロールオーバ", "ログのファイルを時間や大きさで新しくすること", "ノート交換"],
            ["RollingFile（A4）", "Log4j2 のロールオーバつきファイル出力", "交換係つきのノート"],
            ["TimeBasedTriggeringPolicy", "時刻でロールオーバを決める決まり（00 分を過ぎた最初のログで）", "「1 時間たったら交換」の決まり"],
            ["renameEmptyFiles", "空のファイルを改名するか（既定は改名せず削除）", "白紙のノートはしまわずに捨てる決まり"],
            ["ignoreExceptions", "アペンダの失敗をアプリに伝えないか（既定は伝えない）", "ノート係の「書く人を困らせない」約束"],
            ["StatusLogger／DefaultErrorHandler", "Log4j2 自身のエラーを標準エラーに出す仕組み。同じエラーは 5 分に 1 回に間引く", "職員室のメモ帳。同じことは何度も書かない"],
            ["Failover アペンダ", "主のアペンダが失敗したら代わりのアペンダに回す", "ノートに書けなければ連絡帳に書く"],
            ["CURRENT／ARCHIVE／STALE", "診断ツールの判定。正しく書ける／前の時間帯のファイルに書く／Stale", "机のノート／しまったノート／捨てられたノート"],
            ["ECS タスク", "コンテナのまとまり。Fargate ではタスクごとに別の VM", "1 つの班"],
            ["ECS Exec", "動いているコンテナの中でコマンドを実行する仕組み", "班の机をのぞきに行く"],
            ["ELB／ALB のヘルスチェック", "ロードバランサが一定間隔でサーバの健康を確かめる", "先生の見回り"],
            ["Spring MVC の Controller", "HTTP のリクエストを受けて結果を返すクラス", "受付係"],
            ["@ControllerAdvice／@ExceptionHandler", "例外をまとめて HTTP の状態に変える仕組み", "困りごとの受付窓口"],
            ["HTTP 200／500／503", "成功／サーバの中の失敗／いまは受けられない", "元気です／具合が悪い／今は休み中"],
            ["fail-open", "全員が不健康なら、全員に振り分ける ALB の動き", "全員が休みなら、仕方なく全員に回す"],
            ["CloudWatch Logs", "AWS のログの保管・検索サービス", "学校の記録センター"],
            ["CloudTrail", "AWS の操作の記録", "職員室の出入り記録"],
        ], [6, 11, 7], ["l", "l", "l"]),
    ],
}

# ---------------------------------------------------------------------------
# 17 参考資料
# ---------------------------------------------------------------------------
_G = "https://github.com/apache/logging-log4j2/blob/rel/2.25.3/log4j-core/src/main/java/org/apache/logging/log4j/core/"
CH17 = {
    "name": "17_参考資料", "no": "17", "title": "参考資料（2026年10月10日に確認）",
    "lead": "本文の根拠にした一次情報。Log4j2 の行番号は 2.25.3 のソース（Maven Central の sources.jar／GitHub の rel/2.25.3）。",
    "blocks": [
        ("table", ["資料", "URL", "確かめたこと"], [
            ["Log4j2 FileRenameAction（2.25.3）", _G + "appender/rolling/action/FileRenameAction.java", "空なら削除（111・194 行）、Files.move の ATOMIC_MOVE＋REPLACE_EXISTING（209 行）"],
            ["Log4j2 RollingFileManager（2.25.3）", _G + "appender/rolling/RollingFileManager.java", "rollover の順番（閉じる→改名→作成）、最初の交換時刻の基準（913〜932 行）"],
            ["Log4j2 TimeBasedTriggeringPolicy（2.25.3）", _G + "appender/rolling/TimeBasedTriggeringPolicy.java", "00 分を過ぎた最初のイベントで交換（130〜139 行）"],
            ["Log4j2 DefaultErrorHandler（2.25.3）", _G + "appender/DefaultErrorHandler.java", "最初の数件のあとは 5 分に 1 件に間引く（31・99〜113 行）"],
            ["Log4j2 AppenderControl（2.25.3）", _G + "config/AppenderControl.java", "ignoreExceptions=true なら投げ直さない（158〜173 行）"],
            ["Log4j2 RollingFileAppender（2.25.3）", _G + "appender/RollingFileAppender.java", "locking が RollingFileManager に渡されない（79・144〜159 行）"],
            ["Log4j2 LoggerContext（2.25.3）", _G + "LoggerContext.java", "${hostName} を用意する（691 行）"],
            ["log4j-api AbstractLogger（2.25.3）", "https://github.com/apache/logging-log4j2/blob/rel/2.25.3/log4j-api/src/main/java/org/apache/logging/log4j/spi/AbstractLogger.java",
             "ログ呼び出しの中の例外を抑え、LoggingException だけ投げ直す（2962〜2988 行・LOG4J2-1990）"],
            ["Log4j2 マニュアル：Rolling file appenders", "https://logging.apache.org/log4j/2.x/manual/appenders/rolling-file.html", "RollingFileManager の共有は同じ JVM の中だけ、locking の説明"],
            ["Log4j2 マニュアル：File appenders", "https://logging.apache.org/log4j/2.x/manual/appenders/file.html", "append の説明（ローカルディスクの前提）"],
            ["Log4j2 マニュアル：Delegating appenders（Failover）", "https://logging.apache.org/log4j/2.x/manual/appenders/delegating.html", "主のアペンダに ignoreExceptions=false が要る、retryIntervalSeconds の既定 60"],
            ["Log4j リリースノート", "https://logging.apache.org/log4j/2.x/release-notes.html", "2.25.3〜2.26.1 の公開日と変更"],
            ["Apache Logging Services セキュリティ", "https://logging.apache.org/security.html", "CVE-2025-68161・CVE-2026-34477／34478／34480・CVE-2026-49844"],
            ["Maven Central（log4j-core の版の一覧）", "https://repo1.maven.org/maven2/org/apache/logging/log4j/log4j-core/maven-metadata.xml", "最新の版（2.26.1・2.25.5）"],
            ["AWS：EFS の機能（一貫性・ロック）", "https://docs.aws.amazon.com/efs/latest/ug/features.html", "close-to-open、追記は read-after-write の保証外、任意ロックのみ"],
            ["AWS：EFS マウントのトラブルシュート", "https://docs.aws.amazon.com/efs/latest/ug/troubleshooting-efs-mounting.html", "同じ IP で FS を作り直すと bad file handle（アンマウント・再マウントで直る）"],
            ["AWS：EFS の CloudWatch メトリクス", "https://docs.aws.amazon.com/efs/latest/ug/efs-metrics.html", "ClientConnections の意味"],
            ["AWS：ECS で EFS ボリュームを使う", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/efs-volumes.html", "Fargate は PV 1.4.0 以降、監督コンテナがマウントを管理"],
            ["AWS：ECS Exec", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/ecs-exec.html", "動いているタスクでは後から有効にできない、読み取り専用ルートでは使えない"],
            ["AWS：Fargate PV 1.4.0 の発表（2020-04-08）", "https://aws.amazon.com/about-aws/whats-new/2020/04/aws-fargate-launches-platform-version-14/", "Fargate で EFS が使えるようになった時期"],
            ["AWS：タスクメタデータ v4（Fargate）", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-metadata-endpoint-v4-fargate.html", "起動スクリプトでタスク ID を求める"],
            ["AWS：ALB のヘルスチェック", "https://docs.aws.amazon.com/elasticloadbalancing/latest/application/target-group-health-checks.html", "既定 30 秒・5 秒・5 回・2 回・200、全部不健康なら fail-open"],
            ["AWS：ECS のコンテナヘルスチェック", "https://docs.aws.amazon.com/AmazonECS/latest/developerguide/healthcheck.html", "必須コンテナが UNHEALTHY ならタスクが UNHEALTHY"],
            ["LKML：EFS 側の技術者の修正案（2020-11-18）", "https://lkml.iu.edu/hypermail/linux/kernel/2011.2/05183.html", "別のクライアントが開いているファイルを消すと ESTALE、nfsd では再現しない"],
            ["LKML：NFS クライアントのメンテナの返信", "https://lkml.iu.edu/2011.2/05208.html", "NFS4ERR_STALE は「その実体へのアクセスは取り消された」という意味"],
            ["Linux NFS FAQ（A8・A9・A10）", "https://nfs.sourceforge.net/", "close-to-open（2.4.20）、追記は原子的でない、ESTALE の意味"],
            ["Linux man-pages：open(2)", "https://man7.org/linux/man-pages/man2/open.2.html", "O_APPEND は NFS で複数の書き手だと壊れることがある"],
            ["RFC 1094（NFSv2）", "https://www.rfc-editor.org/rfc/rfc1094", "ファイルハンドルとステートレスの設計"],
            ["RFC 1813（NFSv3）", "https://www.rfc-editor.org/rfc/rfc1813", "NFS3ERR_STALE"],
            ["RFC 7530（NFSv4.0）", "https://www.rfc-editor.org/rfc/rfc7530", "OPEN の状態を持つ NFS"],
            ["RFC 8881（NFSv4.1）", "https://www.rfc-editor.org/rfc/rfc8881", "OPEN4_RESULT_PRESERVE_UNLINKED（残すかはサーバ次第）"],
            ["The Twelve-Factor App：Logs", "https://12factor.net/logs", "ログはイベントの流れ（標準出力へ）"],
            ["Red Hat Developer：JBoss EAP 8.1", "https://developers.redhat.com/blog/2025/09/02/jboss-eap-81-modernizing-enterprise-java-applications", "EAP 8.1 の公開（2025 年 9 月）"],
            ["Red Hat：RHEL 9.8 リリースノート", "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/9.8_release_notes/overview", "RHEL 9.8（2026 年 5 月）"],
            ["log4j の歴史（Apache の history）", "https://svn.apache.org/repos/asf/logging/log4j/tags/v_1_1b2/docs/history.html", "1996 年の SEMPER、IBM、2001 年に Apache へ"],
            ["前回の資料（このフォルダの隣）", "C:\\Users\\taka_\\Claude\\Log_Stale_Handle", "2 タスク・gz 圧縮の構成での検証（v1）。今回は 6 タスク・本番の設定で作り直した"],
        ], [6, 10, 8], ["l", "l", "l"]),
    ],
}
