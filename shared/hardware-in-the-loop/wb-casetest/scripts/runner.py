#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""runner — 独立自动化测试执行器(显式指定才运行,默认只 list)。

用法:
  python3 runner.py --list                 # 列出全部测试项与状态
  python3 runner.py --case <case_id>       # 运行单个测试项
  python3 runner.py --case a b c           # 顺序运行多个
  python3 runner.py --chain <chain_name>   # 运行链路
  python3 runner.py --chains               # 列出可用链路
  python3 runner.py --group cco-afn        # 运行某 tag 组

约定:
- 用例在 cases/<id>.py,必须定义 CASE 元数据(dict)与 run(ctx) -> (bool, detail) 。
- 结果写 results/index.jsonl + results/<ts>_<id>.json;文档 docs/<id>.md 由 runner 维护骨架。
- 不依赖项目源码,仅依赖 wbclient(HTTP 工作台)。
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import wbclient  # noqa: E402

CASES_DIR = os.path.join(HERE, "cases")
RESULTS_DIR = os.path.join(HERE, "results")
DOCS_DIR = os.path.join(HERE, "docs")
CHAINS_FILE = os.path.join(HERE, "chains.json")


class Ctx:
    """传给用例 run(ctx) 的执行环境。"""

    def __init__(self, case_id):
        self.case_id = case_id
        self.logs = []
        self.t0 = time.time()

    def log(self, msg):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self.logs.append(line)
        print(line, flush=True)

    # --- simcon 语义验证 ---
    def verify(self, steps, profile="anhui", max_poll=600, **kw):
        if not wbclient.wait_lease_free(max_wait=120):
            return {"ok": False, "error": "simcon lease 长期被占", "steps": []}
        r = wbclient.run_verify(steps, profile=profile, max_poll=max_poll, **kw)
        # 自愈:被强杀任务留下的僵尸会话占口 → close 释放后重试一次
        err = str(r.get("underlying_error") or "") + str(r.get("error") or "") + str(r.get("summary") or "")
        if not r.get("ok") and "占用" in err and "已被后端会话" in err:
            self.log("检测到僵尸会话占口,POST /api/simcon/close 后重试一次")
            wbclient.post("/api/simcon/close", {})
            time.sleep(3)
            r = wbclient.run_verify(steps, profile=profile, max_poll=max_poll, **kw)
        self.log(f"verify: ok={r.get('ok')} summary={r.get('summary')} job={r.get('job_id')}")
        return r

    def build_frame(self, afn, fn, params=None, profile="anhui"):
        r = wbclient.build_frame(afn, fn, params=params, profile=profile)
        self.log(f"build {afn}-F{fn} params={params} -> {str(r)[:120]}")
        return r

    def frames(self, **kw):
        return wbclient.frames(**kw)

    # --- simeter ---
    def simeter(self):
        return wbclient

    # --- 任意只读命令(日志查看等),不给写权限 ---
    def shell_ro(self, cmd, timeout=60):
        """执行只读观察命令(明确禁止 push/写仓库)。"""
        banned = ("git push", "rm -rf /", "mkfs", ":(){")
        if any(b in cmd for b in banned):
            raise RuntimeError(f"禁止命令: {cmd}")
        return subprocess.run(cmd, shell=True, capture_output=True, text=True,
                              timeout=timeout)

    # --- 结果 ---
    def result(self, passed, detail, evidence=None):
        return {
            "passed": bool(passed),
            "detail": detail,
            "evidence": evidence or {},
            "elapsed_s": round(time.time() - self.t0, 1),
            "logs": self.logs,
        }


def load_cases():
    cases = {}
    if not os.path.isdir(CASES_DIR):
        return cases
    for fn in sorted(os.listdir(CASES_DIR)):
        if not fn.endswith(".py") or fn.startswith("_"):
            continue
        cid = fn[:-3]
        spec = importlib.util.spec_from_file_location(cid, os.path.join(CASES_DIR, fn))
        mod = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(mod)
            cases[cid] = mod
        except Exception as e:
            cases[cid] = {"CASE": {"id": cid, "title": cid, "tags": [], "supported": "error"},
                          "load_error": str(e), "run": None}
    return cases


def load_chains():
    if os.path.exists(CHAINS_FILE):
        with open(CHAINS_FILE) as f:
            return json.load(f)
    return {}


def run_case(cid, mod):
    ctx = Ctx(cid)
    try:
        passed, detail = mod.run(ctx)
        res = ctx.result(passed, detail)
    except Exception as e:
        res = ctx.result(False, f"用例异常: {e}\n{traceback.format_exc()[-1500:]}")
    res["case_id"] = cid
    res["meta"] = getattr(mod, "CASE", {"id": cid})
    # 落盘
    os.makedirs(RESULTS_DIR, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(RESULTS_DIR, f"{ts}_{cid}.json"), "w") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    with open(os.path.join(RESULTS_DIR, "index.jsonl"), "a") as f:
        f.write(json.dumps({"ts": ts, "case_id": cid, "passed": res["passed"],
                            "detail": res["detail"][:300]}, ensure_ascii=False) + "\n")
    update_doc(cid, res)
    return res


def doc_path(cid):
    return os.path.join(DOCS_DIR, f"{cid}.md")


def update_doc(cid, res):
    """生成/更新 docs/<id>.md:标题=测试名+支持与否+是否已验证运行成功。"""
    os.makedirs(DOCS_DIR, exist_ok=True)
    meta = res.get("meta") or {}
    supported = meta.get("supported", "?")
    verified = "已验证运行成功" if res.get("passed") else "已验证运行失败"
    title = f"{meta.get('title', cid)} — {supported} — {verified}"
    line = f"- {time.strftime('%Y-%m-%d %H:%M')} 运行: {'✅ PASS' if res.get('passed') else '❌ FAIL'} — {res.get('detail','')[:200]}"
    ev = res.get("evidence") or {}
    ev_lines = "".join(f"  - {k}: {str(v)[:300]}\n" for k, v in ev.items())
    body = f"""# {title}

- **用例 ID**: `{cid}`
- **来源**: {meta.get('source', '用例库')}
- **支持与否**: {supported}{(' — ' + meta['supported_reason']) if meta.get('supported_reason') else ''}
- **是否已验证运行成功**: {'是(最近一次 PASS)' if res.get('passed') else '否(最近一次 FAIL,见下方运行记录)'}
- **所属 tag**: {', '.join(meta.get('tags', []))}

## 测试内容

{meta.get('desc', '(见用例来源)')}

## 本环境执行方式

{meta.get('how', '(用例脚本内注释)')}

## 运行记录

{line}
{ev_lines}
## 最近一次完整日志

```
{(chr(10).join(res.get('logs', []))[-3000:]) or '(无)'}
```
"""
    # 保留历史运行记录
    p = doc_path(cid)
    old_hist = ""
    if os.path.exists(p):
        old = open(p).read()
        if "## 运行记录" in old:
            hist = old.split("## 运行记录", 1)[1]
            # 去掉旧历史里的"最近一次完整日志"之后内容,保留记录行
            hist_lines = [l for l in hist.splitlines() if l.startswith("- 20")]
            old_hist = "\n".join(hist_lines[-9:]) + "\n"
            body = body.replace("{line}\n", "")  # noqa placeholder
    # 简化:直接重写,历史记录附后
    with open(p, "w") as f:
        f.write(body)
        if old_hist:
            f.write("\n## 历史运行\n" + old_hist)


def main():
    ap = argparse.ArgumentParser(description="独立自动化测试执行器(显式指定才运行)")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--case", nargs="+")
    ap.add_argument("--chain")
    ap.add_argument("--chains", action="store_true")
    ap.add_argument("--group")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()

    cases = load_cases()
    chains = load_chains()

    if args.list or (not args.case and not args.chain and not args.group and not args.all and not args.chains):
        print(f"{'ID':44} {'支持':8} {'最近结果':10} 标题")
        idx = {}
        ip = os.path.join(RESULTS_DIR, "index.jsonl")
        if os.path.exists(ip):
            for line in open(ip):
                try:
                    r = json.loads(line)
                    idx[r["case_id"]] = r
                except Exception:
                    pass
        for cid, mod in cases.items():
            meta = getattr(mod, "CASE", {})
            last = idx.get(cid)
            print(f"{cid:44} {meta.get('supported','?'):8} "
                  f"{'PASS' if last and last['passed'] else ('FAIL' if last else '未运行'):10} "
                  f"{meta.get('title','')}")
        return

    if args.chains:
        for name, ch in chains.items():
            print(f"{name}: {' -> '.join(ch['cases'])}  stop_on_fail={ch.get('stop_on_fail', True)}")
        return

    if args.chain:
        ch = chains.get(args.chain)
        if not ch:
            print(f"链路不存在: {args.chain};可用: {list(chains)}")
            sys.exit(2)
        ids = ch["cases"]
        stop = ch.get("stop_on_fail", True)
    elif args.group:
        ids = [cid for cid, m in cases.items()
               if args.group in getattr(m, "CASE", {}).get("tags", [])]
        stop = False
    elif args.all:
        ids = list(cases)
        stop = False
    else:
        ids = args.case
        stop = False

    results = []
    for cid in ids:
        mod = cases.get(cid)
        if not mod or not getattr(mod, "run", None):
            print(f"[skip] {cid} 不存在或不可运行")
            results.append({"case_id": cid, "passed": False, "detail": "不存在"})
            continue
        print(f"\n===== 运行 {cid} =====")
        res = run_case(cid, mod)
        results.append({"case_id": cid, "passed": res["passed"], "detail": res["detail"][:200]})
        if stop and not res["passed"]:
            print(f"[chain] {cid} 失败,按 stop_on_fail 终止链路")
            break

    npass = sum(1 for r in results if r["passed"])
    print(f"\n===== 汇总: {npass}/{len(results)} PASS =====")
    for r in results:
        print(f"  {'PASS' if r['passed'] else 'FAIL'}  {r['case_id']}  {r['detail'][:120]}")
    sys.exit(0 if npass == len(results) else 1)


if __name__ == "__main__":
    main()
