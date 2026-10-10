#!/bin/bash
# =============================================================================
# tracelog-fd-check.sh — Java（JBoss）がいま書いているトレースログの「実体」を調べる
#
#   ECS Exec で各タスクのフロント（またはバック）コンテナに入り、そのまま実行する。
#   6 タスク全部で実行して並べると、「どのタスクが正しく書けていて、どのタスクが Stale か」が一目でわかる。
#
#   使い方:  bash tracelog-fd-check.sh [ログのディレクトリ（リンクでも可）] [現行ファイル名]
#            ディレクトリを省くと、Java の起動引数の -Diwin.log=… を使う（無ければ /webapp/webapp9mf02/logs）
#            現行ファイル名の既定は tracelog
#
#   出力（FD 1 個につき 1 行。集計しやすい key=value 形式）:
#     VERDICT=<判定> host=<ホスト名> pid=<PID> fd=<番号> fd_inode=<i> cur_inode=<i> nlink=<n> name=<実体の今の名前>
#
#   判定:
#     CURRENT     現行ファイル（tracelog）と同じ実体に書いている                     → 正常
#     ARCHIVE     改名済みのファイル（trace.log.*）の実体に書いている                → エラーは出ないが、前の時間帯のファイルに混ざる
#     STALE       実体が EFS 上で消されている                                        → 書くたびに IOException: Stale file handle
#     ORPHAN      実体に名前が無い（nlink=0）                                        → 消された実体に書いている（EFS では次の確認で STALE）
#     NOFD        Java がこのディレクトリのファイルを開いていない
#     NOJAVA      Java のプロセスが見つからない
#     MOUNTSTALE  ディレクトリ（マウントの根元）そのものが Stale                     → EFS 側でディレクトリや FS が作り直された（タスクの入れ替えが必要）
#
#   終了コード: 0 = すべて CURRENT / 1 = ARCHIVE・STALE・ORPHAN がある / 2 = NOFD・NOJAVA・MOUNTSTALE
#
#   注意:
#     - 見るのは「そのディレクトリの直下」の tracelog と trace.log.*（環境変数 ARCHIVE_GLOB で変えられる）だけ。
#       下の mid/{タスクID}/ や、同じディレクトリに置いた server.log・gc.log などは数えない。
#     - ロールオーバの直後（毎時 00 分すぎの 1 分ほど）は、NFS クライアントの名前のキャッシュ（ディレクトリは 30〜60 秒）が古く、
#       ARCHIVE を CURRENT と見誤ることがある。毎時 02 分以降に実行するか、1〜2 分あけて 2 回実行する。
#       ディレクトリが 90 秒以内に変わっていれば、その旨を「# 注意」として出す。STALE の判定は EFS の返事そのものなので、いつでも確か。
#     - 読むだけ（ファイルを開かない・書かない・消さない）。
#     - 必要なもの: bash, coreutils（readlink, stat, timeout, dirname）, grep, sed, tr。UBI 9 の標準イメージに入っている。
# =============================================================================
export LC_ALL=C          # エラーメッセージ（Stale file handle など）を英語に固定して判定する
NAME="${2:-tracelog}"
ARCH_GLOB="${ARCHIVE_GLOB:-trace.log.*}"   # 保存ファイルの名前の形（filePattern に合わせる）
HOST="$(uname -n 2>/dev/null || cat /proc/sys/kernel/hostname 2>/dev/null || echo unknown)"
T=10                     # 1 回の stat を待つ上限（秒）。EFS が応答しないときに固まらないように

out() { echo "VERDICT=$1 host=${HOST} pid=${PID:--} fd=${2:--} fd_inode=${3:--} cur_inode=${CUR:--} nlink=${4:--} name=${5:--}"; }

# --- Java のプロセスを探す（jboss-modules.jar を含むものを優先）
PID=""
for p in /proc/[0-9]*; do
    exe="$(readlink "${p}/exe" 2>/dev/null)" || continue
    [ "${exe##*/}" = "java" ] || continue
    if tr '\0' ' ' < "${p}/cmdline" 2>/dev/null | grep -q 'jboss-modules\.jar'; then PID="${p#/proc/}"; break; fi
    [ -z "${PID}" ] && PID="${p#/proc/}"
done
if [ -z "${PID}" ]; then out NOJAVA; exit 2; fi

# --- 調べるディレクトリ: 引数 → Java の -Diwin.log → 既定
IWIN="$(tr '\0' '\n' < "/proc/${PID}/cmdline" 2>/dev/null | sed -n 's/^-Diwin\.log=//p' | head -n 1)"
DIR="${1:-${IWIN:-/webapp/webapp9mf02/logs}}"

# --- ディレクトリそのものが見えるか（根元が Stale なら、ファイル単位ではなくマウント単位の問題）
chk="$(timeout "${T}" ls -d "${DIR}/" 2>&1)"
case "${chk}" in
    *"Stale file handle"*|*"Stale NFS file handle"*) echo "# ${DIR} が Stale: ${chk}"; out MOUNTSTALE; exit 2 ;;
esac

# --- ディレクトリの実体（リンクをたどる）と、現行ファイルの inode
REAL="$(timeout "${T}" readlink -f "${DIR}" 2>&1)" || { echo "# ${DIR} をたどれない: ${REAL}"; out NOFD; exit 2; }
CUR="$(timeout "${T}" stat -c '%i' "${REAL}/${NAME}" 2>/dev/null)" || CUR=""

# --- Java が開いている FD のうち、このディレクトリ「直下」のファイル
rc=0; found=0
for fd in /proc/"${PID}"/fd/*; do
    tgt="$(readlink "${fd}" 2>/dev/null)" || continue
    tgt="${tgt% (deleted)}"
    [ "$(dirname -- "${tgt}")" = "${REAL}" ] || continue
    # トレースログの名前だけを数える（同じディレクトリの server.log・gc.log などは数えない）
    # shellcheck disable=SC2254
    case "${tgt##*/}" in "${NAME}"|${ARCH_GLOB}) ;; *) continue ;; esac
    found=1
    n="${fd##*/}"
    st="$(timeout "${T}" stat -L -c '%i %h' "${fd}" 2>&1)"; src=$?
    if [ "${src}" -ne 0 ]; then
        case "${st}" in
            *"Stale file handle"*|*"Stale NFS file handle"*) out STALE "${n}" - - "${tgt}"; rc=1 ;;
            *) echo "# fd ${n} を stat できない: ${st}"; out STALE "${n}" - - "${tgt}"; rc=1 ;;
        esac
        continue
    fi
    ino="${st%% *}"; nl="${st##* }"
    if [ -n "${CUR}" ] && [ "${ino}" = "${CUR}" ]; then
        out CURRENT "${n}" "${ino}" "${nl}" "${NAME}"
    elif [ "${nl}" = "0" ]; then
        out ORPHAN "${n}" "${ino}" "${nl}" "(名前なし)"; rc=1
    else
        # 同じ inode の名前を、ディレクトリ直下のファイルから探す（改名済みのファイル）
        who="(不明)"
        for f in "${REAL}"/*; do
            [ -f "${f}" ] || continue
            [ "$(timeout "${T}" stat -c '%i' "${f}" 2>/dev/null)" = "${ino}" ] && { who="${f##*/}"; break; }
        done
        out ARCHIVE "${n}" "${ino}" "${nl}" "${who}"; rc=1
    fi
done
[ "${found}" = 1 ] || { out NOFD; exit 2; }
dm="$(timeout "${T}" stat -c '%Y' "${REAL}" 2>/dev/null)" || dm=""
if [ -n "${dm}" ] && [ $(( $(date +%s) - dm )) -lt 90 ]; then
    echo "# 注意: ${REAL} は $(( $(date +%s) - dm )) 秒前に変わったばかり（ロールオーバの直後）。1〜2 分あけてもう一度実行し、同じ結果か確かめる"
fi
exit "${rc}"
