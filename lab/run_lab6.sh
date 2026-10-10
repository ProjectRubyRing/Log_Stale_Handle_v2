#!/usr/bin/env bash
# =============================================================================
# lab/run_lab6.sh — 「6 タスクが同じ tracelog に書く」構成の再現実験（Docker だけで動く）
#
#   EFS の代わりに Linux カーネルの NFS サーバ（knfsd）を 1 台、ECS タスクの代わりに
#   UBI 9.8 + OpenJDK 21 + Log4j 2.25.3 のコンテナを 6 台立てる。
#   Log4j2 の設定はユーザーのもの（RollingFile A4・TimeBasedTriggeringPolicy・レイアウトなし）。
#   違いはロールオーバの周期だけ（本番 1 時間 → 検証 1 分。filePattern の最小単位を「分」にした）。
#
#   ケース:
#     C1  いまの構成・NFSv3   … 消された実体に Stale を返すサーバ（EFS と同じ振る舞い）
#     C2  いまの構成・NFSv4.1 … knfsd（消されても実体を残すサーバ）。エラーは出ないが行は消える
#     C3  恒久対策・NFSv3     … -Diwin.log を JBoss のログと同じタスクごとのディレクトリ（mid/{タスク}）にする（Log4j2 の設定は同じ）
#     C4  仮説 1・NFSv3       … 動いている最中にファイルシステムを作り直す（中身を消し、別の fsid で出し直す）
#
#   使い方:  bash lab/run_lab6.sh            全ケース（約 20 分）
#            bash lab/run_lab6.sh C1 C3      指定ケースだけ
#            KEEP=1 bash lab/run_lab6.sh C1  終わってもコンテナを残す（手で触る用）
#
#   出力: lab/results/<ケース>/（各タスクの台帳・標準出力・標準エラー、サーバ上のファイル、スナップショット）
#         集計は python lab/analyze.py lab/results/<ケース>
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${HERE}/.." && pwd)"
RES="${HERE}/results"
native() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
export MSYS_NO_PATHCONV=1

NET=estale6-net; VOL=estale6-export
SRV=estale6-nfsd; SRV_IP=172.31.0.10
NT=6
OPT41="vers=4.1,addr=${SRV_IP},hard,timeo=600,retrans=2,noresvport"
OPT3="vers=3,proto=tcp,addr=${SRV_IP},mountaddr=${SRV_IP},mountproto=tcp,mountvers=3,nolock,hard,timeo=600,retrans=2"
JAVA_CP="/opt/lab/classes:/opt/lab/lib/*"
LINK=/webapp/webapp9mf02/logs                 # アプリ（-Diwin.log）が書くパス（シンボリックリンク）
LOGDIR=/mnt/logs/front/logs/inter-api         # リンク先（EFS 上の共有ディレクトリ。下に mid/{タスク} がある）
SRVDIR=/export/front/logs/inter-api           # サーバ側から見た同じディレクトリ

task() { echo "estale6-t$1"; }
ts() { date '+%H:%M:%S'; }
say() { echo "[$(ts)] $*"; }

# ------------------------------------------------------------------ 基盤
build_images() {
    say "イメージを作る"
    docker build -q -t estale-nfsd:local "$(native "${HERE}/server")" >/dev/null
    docker build -q -t estale6-client:local -f "$(native "${HERE}/client/Dockerfile")" "$(native "${HERE}")" >/dev/null
}

server_down() {
    docker exec "${SRV}" sh -c 'rpc.nfsd 0; exportfs -ua' >/dev/null 2>&1 || true
    docker stop -t 20 "${SRV}" >/dev/null 2>&1 || true
    docker rm -f "${SRV}" >/dev/null 2>&1 || true
}

server_up() {      # server_up [fsid]
    server_down
    docker run -d --name "${SRV}" --hostname nfsd --privileged --network "${NET}" --ip "${SRV_IP}" \
        -e EXPORT_FSID="${1:-0}" -v "${VOL}:/export" estale-nfsd:local >/dev/null
    for _ in $(seq 1 30); do
        if docker logs "${SRV}" 2>&1 | grep -q 'READY'; then
            sleep 12          # NFSv4 の猶予期間（10 秒に縮めてある）が明けるのを待つ
            return 0
        fi
        sleep 1
    done
    echo "NFS サーバが起動しない" >&2; docker logs "${SRV}" >&2; return 1
}

clients_down() {
    local i
    for i in $(seq 1 "${NT}"); do
        docker exec "$(task "$i")" sh -c 'pkill -f TraceLab; umount -f -l /mnt/logs' >/dev/null 2>&1 || true
        docker rm -f "$(task "$i")" >/dev/null 2>&1 || true
    done
}

infra_up() {
    clients_down
    server_down
    docker network inspect "${NET}" >/dev/null 2>&1 || docker network create --subnet 172.31.0.0/24 "${NET}" >/dev/null
    docker volume inspect "${VOL}" >/dev/null 2>&1 || docker volume create "${VOL}" >/dev/null
    server_up 0
}

infra_down() {
    [ "${KEEP:-0}" = 1 ] && return 0
    clients_down
    server_down
    docker network rm "${NET}" >/dev/null 2>&1 || true
    docker volume rm "${VOL}" >/dev/null 2>&1 || true
}

# ケースごとに 6 タスクを作り直し、サーバ側をまっさらにする
clients_up() {     # clients_up <3|4.1>
    local v="$1" i o t p
    clients_down
    # 前のケース（C4）で fsid を変えたままなら、fsid=0（NFSv4 の疑似ルート）に戻す
    if ! docker inspect -f '{{range .Config.Env}}{{println .}}{{end}}' "${SRV}" 2>/dev/null | grep -qx 'EXPORT_FSID=0'; then
        server_up 0
    fi
    docker exec "${SRV}" sh -c "rm -rf /export/* /export/.[!.]* 2>/dev/null; mkdir -p ${SRVDIR}/mid; chmod -R 777 /export/front"
    if [ "${v}" = "3" ]; then o="${OPT3}"; t=nfs; p=/export; else o="${OPT41}"; t=nfs4; p=/; fi
    for i in $(seq 1 "${NT}"); do
        docker run -d --name "$(task "$i")" --hostname "task-${i}" --privileged --network "${NET}" \
            --ip "172.31.0.$((20 + i))" -v "$(native "${ROOT}/tools"):/opt/tools:ro" estale6-client:local >/dev/null
        docker exec "$(task "$i")" bash -c "mount -i -t ${t} -o ${o} ${SRV_IP}:${p} /mnt/logs && test -d ${LOGDIR}"
    done
}

# 次の「分の境目 + off 秒」まで待つ
wait_sec_of_minute() {   # wait_sec_of_minute <秒>
    local now s
    now="$(date +%s)"; s=$((now % 60))
    if [ "${s}" -lt "$1" ]; then sleep $(($1 - s)); else sleep $((60 - s + $1)); fi
}

start_java() {     # start_java <番号> <秒> [iwin.log の値。{T} はタスク名に置き換える]
    local i="$1" n="T$1" iw="${3:-${LINK}}"
    iw="${iw//\{T\}/T$1}"
    docker exec -d -e TASK_NAME="${n}" -e DURATION_SEC="$2" -e SEED="$((i * 7919))" -e MIN_MS=100 -e MAX_MS=400 \
        "$(task "$i")" bash -c "mkdir -p ${iw} && java -Diwin.log=${iw} -Dlog4j2.configurationFile=/opt/lab/conf/log4j2-current.xml -cp '${JAVA_CP}' TraceLab > /tmp/stdout.log 2> /tmp/stderr.log"
}

# スナップショット: 各タスクで診断ツール、サーバ側で実体の一覧（inode・リンク数・大きさ・更新時刻・名前）
snapshot() {       # snapshot <出力ファイル>
    local f="$1" i
    {
        echo "# snapshot $(date '+%Y-%m-%d %H:%M:%S')"
        for i in $(seq 1 "${NT}"); do
            echo "## T${i}"
            docker exec "$(task "$i")" bash /opt/tools/tracelog-fd-check.sh 2>&1 || true
        done
        echo "## SERVER"
        docker exec "${SRV}" sh -c "cd ${SRVDIR} 2>/dev/null && find . -type f -exec stat -c '%i %h %s %Y %n' {} +" 2>&1 || true
    } > "${f}"
}

# Java が終わるまで待つ（最大 limit 秒）
wait_java() {      # wait_java <limit>
    local end=$(( $(date +%s) + $1 )) i busy
    while [ "$(date +%s)" -lt "${end}" ]; do
        busy=0
        for i in $(seq 1 "${NT}"); do
            docker exec "$(task "$i")" pgrep -f TraceLab >/dev/null 2>&1 && busy=1
        done
        [ "${busy}" = 0 ] && return 0
        sleep 2
    done
    say "Java が時間内に終わらない"
}

collect() {        # collect <ケースのディレクトリ>
    local d="$1" i
    for i in $(seq 1 "${NT}"); do
        mkdir -p "${d}/T${i}"
        for x in ledger.tsv stdout.log stderr.log; do
            docker cp "$(task "$i"):/tmp/${x}" "$(native "${d}/T${i}/${x}")" >/dev/null 2>&1 || true
        done
    done
    rm -rf "${d}/export"; mkdir -p "${d}/export"
    docker exec "${SRV}" sh -c 'cd /export && tar cf - . 2>/dev/null' | tar xf - -C "${d}/export" 2>/dev/null || true
}

# ------------------------------------------------------------------ ケース
# run_case <id> <NFS 版> <秒> <説明> [-Diwin.log の値（{T} はタスク名）] [途中の割り込み（秒,関数）]
run_case() {
    local id="$1" v="$2" dur="$3" desc="$4" iwin="${5:-}" hook="${6:-}"
    local d="${RES}/${id}" i start end next
    rm -rf "${d}"; mkdir -p "${d}"
    say "=== ${id}: ${desc}（NFSv${v}・${NT} タスク・${dur} 秒）"
    clients_up "${v}"
    wait_sec_of_minute 20                               # 分の 20 秒に始め、最初の境目まで 40 秒あける
    start="$(date +%s)"
    for i in $(seq 1 "${NT}"); do start_java "${i}" "${dur}" "${iwin}"; done
    printf 'id=%s\nnfs=%s\ntasks=%s\nduration=%s\nstart_epoch=%s\ndesc=%s\n' "${id}" "${v}" "${NT}" "${dur}" "${start}" "${desc}" > "${d}/meta.txt"
    end=$((start + dur))
    local hook_at="" hook_fn="" hooked=0
    if [ -n "${hook}" ]; then hook_at=$((start + ${hook%%,*})); hook_fn="${hook#*,}"; fi
    # 各境目の 25 秒後にスナップショット（境目 = 分の 0 秒）
    while :; do
        next=$(( ( $(date +%s) / 60 + 1 ) * 60 + 25 ))
        if [ -n "${hook_at}" ] && [ "${hooked}" = 0 ] && [ "${hook_at}" -lt "${next}" ] && [ "${hook_at}" -lt "${end}" ]; then
            sleep $(( hook_at - $(date +%s) > 0 ? hook_at - $(date +%s) : 0 ))
            say "割り込み: ${hook_fn}"; "${hook_fn}" "${d}"; hooked=1
            continue
        fi
        [ "${next}" -ge $((end - 2)) ] && break
        sleep $(( next - $(date +%s) ))
        say "スナップショット $(date '+%H:%M:%S')"
        snapshot "${d}/snap-$(date '+%H%M%S').txt"
    done
    wait_java $((end - $(date +%s) + 40))
    collect "${d}"
    echo "end_epoch=$(date +%s)" >> "${d}/meta.txt"
    say "収集した: ${d}"
}

# C4 の割り込み: 動いている最中にファイルシステムを作り直す（中身を消して、別の fsid で出し直す = 同じ IP の新しい FS）
recreate_fs() {
    local d="$1"
    snapshot "${d}/snap-before-recreate.txt"
    server_down
    docker run --rm -v "${VOL}:/export" debian:bookworm-slim sh -c 'rm -rf /export/* /export/.[!.]*; mkdir -p /export/front/logs/inter-api/mid; chmod -R 777 /export/front' >/dev/null
    server_up 7
    echo "recreate_epoch=$(date +%s)" >> "${d}/meta.txt"
    sleep 5
    {
        local i
        for i in $(seq 1 "${NT}"); do
            echo "## T${i}"
            docker exec "$(task "$i")" bash -c "LC_ALL=C ls ${LINK}/ 2>&1 | head -3; LC_ALL=C ls /mnt/logs 2>&1 | head -3" || true
        done
    } > "${d}/after-recreate-ls.txt"
}

C1() { run_case C1 3   250 "いまの構成（6 タスクが同じ tracelog）"; }
C2() { run_case C2 4.1 250 "いまの構成（6 タスクが同じ tracelog）"; }
C3() { run_case C3 3   190 "恒久対策（-Diwin.log を JBoss と同じ mid/{タスク} に）" "${LOGDIR}/mid/{T}"; }
C4() { run_case C4 3   130 "仮説 1（動いている最中にファイルシステムを作り直す）" "" "55,recreate_fs"; }

main() {
    local cases=("$@")
    [ "${#cases[@]}" -eq 0 ] && cases=(C1 C2 C3 C4)
    mkdir -p "${RES}"
    build_images
    infra_up
    trap infra_down EXIT
    {
        echo "date=$(date '+%Y-%m-%d %H:%M:%S %z')"
        echo "docker=$(docker version --format '{{.Server.Version}}') kernel=$(docker info --format '{{.KernelVersion}}')"
        docker run --rm estale6-client:local bash -c 'echo "client=$(cat /etc/redhat-release) java=$(java -version 2>&1 | head -1) log4j=${LOG4J_VERSION}"'
        echo "server=Debian $(docker run --rm --entrypoint cat estale-nfsd:local /etc/debian_version 2>/dev/null) knfsd（Docker の VM のカーネル）"
    } > "${RES}/meta.txt" 2>&1 || true
    local c
    for c in "${cases[@]}"; do "${c}"; done
    say "おわり"
}

main "$@"
