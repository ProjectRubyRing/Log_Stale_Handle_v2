# -*- coding: utf-8 -*-
"""lab/results/<ケース>/analysis.json（lab/analyze.py が作る）を読み、本文で使う数字を返す"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
RES = os.path.abspath(os.path.join(HERE, "..", "lab", "results"))


RES1 = os.path.abspath(os.path.join(HERE, "..", "lab", "results_run1"))
RES2 = os.path.abspath(os.path.join(HERE, "..", "lab", "results_run2"))


def load(case, run=3):
    """run=3: lab/results（3 回目・本番と同じ配置）、2: lab/results_run2、1: lab/results_run1（旧い配置）"""
    p = os.path.join({1: RES1, 2: RES2, 3: RES}[run], case, "analysis.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def boundary_rows(r):
    """境目ごとの [境目, 順番, CURRENT 数, ARCHIVE 数, STALE 数, 正しく書けたタスク, 最後のタスク]"""
    rows = []
    if not r:
        return rows
    for b in r["boundaries"]:
        if b.get("after_recreate"):
            continue
        mk = None
        for k in r["fates"]:
            if k.endswith(b["boundary_utc"][:5].replace(":", "-")):
                mk = k
        if not mk:
            continue
        f = r["fates"][mk]
        cnt = {}
        for v in f.values():
            cnt[v] = cnt.get(v, 0) + 1
        cur = [t for t, v in f.items() if v == "CURRENT"]
        arc = [t for t, v in f.items() if v == "ARCHIVE"]
        rows.append({"b": b["boundary_utc"], "order": b["order"], "offset": b["offset_ms"],
                     "cur": cur, "arc": arc, "n_cur": cnt.get("CURRENT", 0), "n_arc": cnt.get("ARCHIVE", 0),
                     "n_stale": cnt.get("STALE", 0) + cnt.get("ORPHAN", 0), "n_mixed": cnt.get("MIXED", 0),
                     "last": b["order"][-1] if b["order"] else "-"})
    return rows


def tool_accuracy(r):
    """スナップショットの判定がサーバ側の実体と一致した数 (一致, 全体)"""
    if not r:
        return 0, 0
    a = sum(s.get("agree", 0) for s in r["snapshots"] if s.get("truth"))
    n = sum(s.get("of", 0) for s in r["snapshots"] if s.get("truth"))
    return a, n


def meta():
    p = os.path.join(RES, "meta.txt")
    m = {}
    if os.path.exists(p):
        for ln in open(p, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if ln.startswith("date="):
                m["date"] = ln[5:]
            elif ln.startswith("docker="):
                m["docker"] = ln[7:]
            elif ln.startswith("client="):
                m["client"] = ln[7:]
            elif ln.startswith("server="):
                m["server"] = ln[7:]
    return m


def pct(a, b):
    return "%.1f%%" % (100.0 * a / b) if b else "-"


def totals(r):
    t = r["totals"]
    e = t.get("emitted", 0)
    return {
        "emitted": e, "ok": t.get("ok", 0), "mis": t.get("misplaced", 0), "lost": t.get("lost", 0),
        "ok_p": pct(t.get("ok", 0), e), "mis_p": pct(t.get("misplaced", 0), e), "lost_p": pct(t.get("lost", 0), e),
    }


def stale_shown(r):
    return sum(v.get("stale", 0) for v in r["stderr"].values())


def server_log(r):
    s = r["server_log"]
    return sum(v["expected"] for v in s.values()), sum(v["found"] for v in s.values())


def snap_counts(r):
    """スナップショットごとの判定の集計 [(ファイル名, {判定: 数}, 予想との一致)]"""
    out = []
    for s in r["snapshots"]:
        out.append((s["file"], s["count"], s.get("match"), s["verdicts"]))
    return out
