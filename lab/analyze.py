# -*- coding: utf-8 -*-
"""
lab/analyze.py — run_lab6.sh の結果を集計する

  python lab/analyze.py lab/results/C1 [lab/results/C2 ...]

  - 台帳（各タスクが「いつ・何番を書いたか」）と、NFS サーバ上に残った行を突き合わせ、
    行ごとに「正しいファイルに残った / 別の時間帯のファイルに入った / 消えた」を数える。
  - 境目ごとに、各タスクのロールオーバの順番（境目を過ぎて最初に書いた時刻の順）を出し、
    「最後にロールオーバしたタスクだけが tracelog に正しく書ける。最後から 2 番目は前の時間帯のファイルに書く。
     それより前のタスクは Stale」という予想と、スナップショット（診断ツールの判定）を比べる。
  - 標準エラー（Log4j2 の StatusLogger）に出た「Stale file handle」の回数と、実際に失われた行数を比べる
    （DefaultErrorHandler が「最初の数件のあとは 5 分に 1 回」に間引くため、ログに出る回数は実際よりずっと少ない）。

  出力: <ケース>/analysis.json と <ケース>/analysis.md（日本語の要約）
"""
import datetime as dt
import glob
import json
import os
import re
import sys
from collections import Counter, defaultdict

LINE = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) task=(T\d+) seq=(\d+)$")
SLINE = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) task=(T\d+) server seq=(\d+)$")
VERD = re.compile(r"^VERDICT=(\S+) host=(\S+) pid=(\S+) fd=(\S+) fd_inode=(\S+) cur_inode=(\S+) nlink=(\S+) name=(.*)$")


def utc(ms):
    return dt.datetime.fromtimestamp(ms / 1000.0, tz=dt.timezone.utc)


def minute_key(ms):
    return utc(ms).strftime("%Y-%m-%d-%H-%M")


def read_meta(d):
    m = {}
    p = os.path.join(d, "meta.txt")
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8", errors="replace"):
            if "=" in ln:
                k, v = ln.rstrip("\n").split("=", 1)
                m[k] = v
    return m


def read_ledger(p):
    out = []
    if not os.path.exists(p):
        return out
    for ln in open(p, encoding="utf-8", errors="replace"):
        parts = ln.split()
        if len(parts) == 2 and parts[0].isdigit():
            out.append((int(parts[0]), int(parts[1])))
    return out


def read_files(root, pattern_re, want=lambda n: True):
    """root 以下のファイル（名前が want に合うもの）を読み、(task, seq) -> [ファイル名...]、壊れた行の数を返す"""
    where = defaultdict(list)
    broken = Counter()
    nul = Counter()
    sizes = {}
    for p in sorted(glob.glob(os.path.join(root, "**", "*"), recursive=True)):
        if not os.path.isfile(p) or not want(os.path.basename(p)):
            continue
        rel = os.path.relpath(p, root).replace("\\", "/")
        data = open(p, "rb").read()
        sizes[rel] = len(data)
        nul[rel] = data.count(b"\x00")
        for raw in data.split(b"\n"):
            if not raw:
                continue
            s = raw.replace(b"\x00", b"").decode("utf-8", "replace")
            mm = pattern_re.match(s)
            if mm:
                where[(mm.group(2), int(mm.group(3)))].append(rel)
            else:
                broken[rel] += 1
    return where, broken, nul, sizes


def stderr_stats(p):
    st = Counter()
    first = []
    if not os.path.exists(p):
        return st, first
    for ln in open(p, encoding="utf-8", errors="replace"):
        s = ln.rstrip("\n")
        if "Stale file handle" in s:
            st["stale"] += 1
        if "Unable to write to stream" in s:
            if "/server.log" in s:
                st["write_err_server"] += 1
            else:
                st["write_err_trace"] += 1
        if "Unable to close stream" in s:
            st["close_err"] += 1
        if "Failed to create file after rollover" in s:
            st["create_err"] += 1
        if "Unable to" in s or "Error writing" in s or "Caused by" in s:
            if len(first) < 12:
                first.append(s[:240])
    return st, first


def parse_snapshot(p):
    snap = {"tasks": {}, "server": {}, "time": None}
    cur = None
    for ln in open(p, encoding="utf-8", errors="replace"):
        s = ln.rstrip("\n")
        if s.startswith("# snapshot"):
            snap["time"] = s.split(" ", 2)[2]
        elif s.startswith("## "):
            cur = s[3:].strip()
        elif cur == "SERVER":
            parts = s.split(" ", 4)
            if len(parts) == 5 and parts[0].isdigit():
                nm = parts[4][2:] if parts[4].startswith("./") else parts[4]
                snap["server"][parts[0]] = {"nlink": parts[1], "size": parts[2], "mtime": parts[3], "name": nm}
        elif cur:
            mm = VERD.match(s)
            if mm:
                snap["tasks"].setdefault(cur, []).append({
                    "verdict": mm.group(1), "fd_inode": mm.group(5), "cur_inode": mm.group(6),
                    "nlink": mm.group(7), "name": mm.group(8)})
    return snap


def analyze(d):
    meta = read_meta(d)
    tasks = sorted([os.path.basename(x) for x in glob.glob(os.path.join(d, "T*")) if os.path.isdir(x)],
                   key=lambda t: int(t[1:]))
    ledgers = {t: read_ledger(os.path.join(d, t, "ledger.tsv")) for t in tasks}
    # 共有ディレクトリ（front/logs/inter-api）の下を全部読み、名前で分ける（mid/{タスク} の server.log もこの下にある）
    base = os.path.join(d, "export", "front", "logs", "inter-api")
    if not os.path.isdir(base):                       # 1・2 回目の実験（古い配置）
        base = os.path.join(d, "export", "front", "inter-api")
    where, broken, nul, sizes = read_files(base, LINE, lambda n: n == "tracelog" or n.startswith("trace.log."))
    swhere, sbroken, snul, ssizes = read_files(base, SLINE, lambda n: n.startswith("server.log"))

    start = int(meta.get("start_epoch", "0"))
    recreate = int(meta["recreate_epoch"]) if "recreate_epoch" in meta else None
    all_ms = [ms for t in tasks for _, ms in ledgers[t]]
    if not all_ms:
        return {"error": "台帳が無い"}
    first_ms, last_ms = min(all_ms), max(all_ms)
    last_minute = minute_key(last_ms)

    # ---- 行ごとの行き先
    per_task = {}
    per_minute = defaultdict(lambda: defaultdict(Counter))   # minute -> task -> {emitted, ok, misplaced, lost}
    for t in tasks:
        c = Counter()
        for seq, ms in ledgers[t]:
            mk = minute_key(ms)
            files = where.get((t, seq), [])
            # その行が本来入るべきファイル名（ケース C3 はタスクごとのディレクトリの下にある）
            right = "tracelog" if mk == last_minute else "trace.log.%s" % mk
            names = [f.split("/")[-1] for f in files]
            c["emitted"] += 1
            per_minute[mk][t]["emitted"] += 1
            if not files:
                c["lost"] += 1
                per_minute[mk][t]["lost"] += 1
            elif right in names:
                c["ok"] += 1
                per_minute[mk][t]["ok"] += 1
            else:
                c["misplaced"] += 1
                per_minute[mk][t]["misplaced"] += 1
            if len(files) > 1:
                c["dup"] += 1
        per_task[t] = dict(c)

    # ---- server.log（タスクごとのディレクトリ。単独の書き手）
    server = {}
    for t in tasks:
        exp = [seq for seq, _ in ledgers[t] if seq % 10 == 0]
        got = sum(1 for seq in exp if (t, seq) in swhere)
        server[t] = {"expected": len(exp), "found": got}

    # ---- ファイルごとの中身（どのタスクの、どの分の行が入っているか）
    comp = defaultdict(lambda: {"tasks": Counter(), "minutes": Counter()})
    ms_of = {(t, seq): ms for t in tasks for seq, ms in ledgers[t]}
    for (t, seq), files in where.items():
        for f in files:
            comp[f]["tasks"][t] += 1
            if (t, seq) in ms_of:
                comp[f]["minutes"][minute_key(ms_of[(t, seq)])] += 1

    # ---- (タスク, 分) ごとの「行の行き先」から見た状態（その分のあいだ、どこに書けていたか）
    def fate(c):
        e = c.get("emitted", 0)
        if not e:
            return "-"
        for k, name in (("ok", "CURRENT"), ("misplaced", "ARCHIVE"), ("lost", "STALE")):
            if c.get(k, 0) >= 0.9 * e:
                return name
        return "MIXED"
    fates = {mk: {t: fate(c) for t, c in v.items()} for mk, v in per_minute.items()}

    # ---- 作り直し（C4）の後に書いた行
    post = None
    if recreate:
        rms = recreate * 1000
        pe = sum(1 for t in tasks for seq, ms in ledgers[t] if ms > rms)
        pf = sum(1 for t in tasks for seq, ms in ledgers[t] if ms > rms and (t, seq) in where)
        se = sum(1 for t in tasks for seq, ms in ledgers[t] if ms > rms and seq % 10 == 0)
        sf = sum(1 for t in tasks for seq, ms in ledgers[t] if ms > rms and seq % 10 == 0 and (t, seq) in swhere)
        post = {"trace_emitted": pe, "trace_found": pf, "server_emitted": se, "server_found": sf}

    # ---- 境目ごとのロールオーバ順（境目を過ぎて最初に書いた時刻）
    boundaries = []
    b = (first_ms // 60000 + 1) * 60000
    while b <= last_ms:
        order = []
        for t in tasks:
            after = [ms for _, ms in ledgers[t] if ms >= b]
            if after:
                order.append((min(after), t))
        order.sort()
        pred = {}
        for k, (_, t) in enumerate(order):
            if k == len(order) - 1:
                pred[t] = "CURRENT"
            elif k == len(order) - 2:
                pred[t] = "ARCHIVE"
            else:
                pred[t] = "STALE" if meta.get("nfs") == "3" else "ORPHAN"
        boundaries.append({
            "boundary_utc": utc(b).strftime("%H:%M:%S"),
            "order": [t for _, t in order],
            "offset_ms": [ms - b for ms, _ in order],
            "predicted": pred,
            "after_recreate": bool(recreate and b > recreate * 1000),
        })
        b += 60000

    # ---- スナップショット
    snaps = []
    for p in sorted(glob.glob(os.path.join(d, "snap-*.txt"))):
        s = parse_snapshot(p)
        name = os.path.basename(p)
        verdicts = {t: (v[0]["verdict"] if v else "NOFD") for t, v in s["tasks"].items()}
        # 正解（サーバ側の一覧で、FD の実体の今の名前を引く。STALE は EFS／サーバの返事そのものなので正解とみなす）
        truth = {}
        for t, v in s["tasks"].items():
            if not v:
                truth[t] = "NOFD"
                continue
            x = v[0]
            if x["verdict"] in ("STALE", "MOUNTSTALE", "NOFD", "NOJAVA"):
                truth[t] = x["verdict"]
            elif x["fd_inode"] in s["server"]:
                nm = s["server"][x["fd_inode"]]["name"].split("/")[-1]
                truth[t] = "CURRENT" if nm == "tracelog" else ("ARCHIVE" if nm.startswith("trace.log.") else "OTHER")
            else:
                truth[t] = "ORPHAN"
        agree_srv = sum(1 for t in verdicts if verdicts[t] == truth.get(t))
        # 予想との突き合わせ（スナップショット直前の境目）
        match = None
        if s["time"] and boundaries and name.startswith("snap-") and name[5:11].isdigit():
            hh, mi, ss = int(name[5:7]), int(name[7:9]), int(name[9:11])
            bt = "%02d:%02d:00" % (hh, mi) if ss >= 20 else None
            for bd in boundaries:
                if bt and bd["boundary_utc"].endswith(bt[3:]) and not bd["after_recreate"]:
                    # 時は TZ の違いがあるので分:秒で照合
                    pred = bd["predicted"]
                    agree = sum(1 for t in tasks if verdicts.get(t) == pred.get(t))
                    match = {"boundary_utc": bd["boundary_utc"], "agree": agree, "of": len(tasks)}
        cnt = Counter(verdicts.values())
        snaps.append({"file": name, "verdicts": verdicts, "truth": truth, "agree": agree_srv, "of": len(verdicts),
                      "count": dict(cnt), "match": match, "server": s["server"]})

    stderr = {}
    samples = {}
    for t in tasks:
        st, first = stderr_stats(os.path.join(d, t, "stderr.log"))
        stderr[t] = dict(st)
        samples[t] = first

    tot = Counter()
    for t in tasks:
        tot.update(per_task[t])
    res = {
        "meta": meta, "tasks": tasks, "totals": dict(tot), "per_task": per_task,
        "per_minute": {m: {t: dict(c) for t, c in v.items()} for m, v in sorted(per_minute.items())},
        "server_log": server, "files": {f: {"tasks": dict(v["tasks"]), "minutes": dict(v["minutes"]),
                                            "size": sizes.get(f), "nul": nul.get(f, 0), "broken": broken.get(f, 0)}
                                        for f, v in sorted(comp.items())},
        "broken_lines": dict(broken), "nul_bytes": {k: v for k, v in nul.items() if v},
        "boundaries": boundaries, "snapshots": snaps, "stderr": stderr, "stderr_samples": samples,
        "last_minute": last_minute, "fates": fates, "post_recreate": post,
    }
    with open(os.path.join(d, "analysis.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    write_md(d, res)
    return res


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def write_md(d, r):
    m = r["meta"]
    L = ["# %s  %s（NFSv%s・%s タスク・%s 秒）" % (m.get("id"), m.get("desc"), m.get("nfs"), m.get("tasks"), m.get("duration")), ""]
    t = r["totals"]
    L.append("- 書いた行（全タスク）: %d / 正しいファイルに残った: %d（%s）/ 別の時間帯のファイルに入った: %d（%s）/ 消えた: %d（%s）"
             % (t.get("emitted", 0), t.get("ok", 0), pct(t.get("ok", 0), t.get("emitted", 0)),
                t.get("misplaced", 0), pct(t.get("misplaced", 0), t.get("emitted", 0)),
                t.get("lost", 0), pct(t.get("lost", 0), t.get("emitted", 0))))
    sl = r["server_log"]
    L.append("- server.log（タスクごとのディレクトリ・単独の書き手）: 期待 %d 行 / 残った %d 行"
             % (sum(v["expected"] for v in sl.values()), sum(v["found"] for v in sl.values())))
    L.append("")
    L.append("## タスクごと")
    L.append("")
    L.append("| タスク | 書いた | 正しい | 別の時間帯 | 消えた | 書き込み失敗の表示（A4） | 閉じる失敗の表示 | server.log 期待/残り |")
    L.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for k in r["tasks"]:
        p = r["per_task"][k]
        L.append("| %s | %d | %d | %d | %d | %d | %d | %d/%d |" % (
            k, p.get("emitted", 0), p.get("ok", 0), p.get("misplaced", 0), p.get("lost", 0),
            r["stderr"][k].get("write_err_trace", 0), r["stderr"][k].get("close_err", 0), sl[k]["expected"], sl[k]["found"]))
    L.append("")
    L.append("## 境目ごとのロールオーバ順と、その分の実際の状態（行の行き先から）")
    L.append("")
    for b in r["boundaries"]:
        mk = None
        for k in r["fates"]:
            if k.endswith(b["boundary_utc"][:5].replace(":", "-")):
                mk = k
        L.append("- %s（UTC）順番: %s（境目からの遅れ ms: %s）%s" % (
            b["boundary_utc"], " → ".join(b["order"]), ", ".join(str(x) for x in b["offset_ms"]),
            "（作り直しの後）" if b["after_recreate"] else ""))
        if mk:
            L.append("  実際: " + ", ".join("%s=%s" % (k, v) for k, v in sorted(r["fates"][mk].items(), key=lambda x: int(x[0][1:]))))
    if r.get("post_recreate"):
        p = r["post_recreate"]
        L.append("")
        L.append("- 作り直しの後に書いた行: トレース %d 行中 %d 行が残った / server.log %d 行中 %d 行が残った" % (
            p["trace_emitted"], p["trace_found"], p["server_emitted"], p["server_found"]))
    L.append("")
    L.append("## スナップショット（診断ツール tools/tracelog-fd-check.sh の判定）")
    L.append("")
    for s in r["snapshots"]:
        diff = ["%s（ツール %s／実際 %s）" % (k, s["verdicts"][k], s["truth"].get(k)) for k in s["verdicts"] if s["verdicts"][k] != s["truth"].get(k)]
        L.append("- %s: %s  集計 %s  サーバ側の実体と一致 %d/%d%s" % (
            s["file"], ", ".join("%s=%s" % (k, v) for k, v in sorted(s["verdicts"].items(), key=lambda x: int(x[0][1:]))),
            s["count"], s["agree"], s["of"], ("  不一致: " + " ".join(diff)) if diff else ""))
    L.append("")
    L.append("## 分ごと（書いた / 正しい / 別の時間帯 / 消えた）")
    L.append("")
    L.append("| 分（UTC） | " + " | ".join(r["tasks"]) + " |")
    L.append("|---|" + "---|" * len(r["tasks"]))
    for mk, v in r["per_minute"].items():
        cells = []
        for k in r["tasks"]:
            c = v.get(k, {})
            cells.append("%d/%d/%d/%d" % (c.get("emitted", 0), c.get("ok", 0), c.get("misplaced", 0), c.get("lost", 0)))
        L.append("| %s | %s |" % (mk[-5:], " | ".join(cells)))
    L.append("")
    L.append("## ファイルごとの中身（どのタスクの・どの分の行か）")
    L.append("")
    for f, v in r["files"].items():
        L.append("- %s: タスク %s / 分 %s / 大きさ %s / NUL %s / 壊れた行 %s" % (
            f, dict(sorted(v["tasks"].items())), dict(sorted(v["minutes"].items())), v["size"], v["nul"], v["broken"]))
    L.append("")
    L.append("## 標準エラーの例（Log4j2 StatusLogger）")
    L.append("")
    for k in r["tasks"]:
        if r["stderr_samples"][k]:
            L.append("### " + k)
            L.append("```")
            L.extend(r["stderr_samples"][k][:8])
            L.append("```")
            break
    with open(os.path.join(d, "analysis.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


def main():
    for d in sys.argv[1:]:
        r = analyze(d)
        p = os.path.join(d, "analysis.md")
        print(open(p, encoding="utf-8").read() if os.path.exists(p) else r)


if __name__ == "__main__":
    main()
