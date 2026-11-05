#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""金样例用例:CCO 03H-F1 厂商代码和版本信息查询(供其余用例照抄结构)。"""

CASE = {
    "id": "cco_03f1_vendor_version",
    "title": "CCO 03H-F1 厂商代码和版本信息查询",
    "source": "用例库/CCO/台账/145_国网用例_AFN功能_初始化与查询_台账.md 行50 (AFN=03H-F1厂商代码和版本信息)",
    "supported": "yes",
    "supported_reason": "simcon 语义构帧支持 03-F1;CCO 实板在网,实探已回应答帧",
    "tags": ["cco-afn", "smoke"],
    "desc": "模拟集中器下发 AFN=03H-F1 查询,预期 CCO 正确返回厂商代码和版本信息,帧格式正确。",
    "how": "v2 verification-runs 单步 send(03,F1) + expect(03,F1);判据=matched 帧 AFN=03/DT=F1 且解析成功。",
}


def run(ctx):
    r = ctx.verify([
        {"name": "query_03f1",
         "send": {"afn": "03", "fn": 1, "params": {}},
         "expect": {"afn": "03", "fn": 1},
         "expect_timeout": 8},
    ])
    if not r.get("ok"):
        return False, f"验证任务未通过: {r.get('summary') or r.get('error')}"
    s = r["steps"][0]
    matched = s.get("matched", "")
    return True, f"CCO 应答 03H-F1: {matched[:80]}"
