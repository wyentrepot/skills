#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_wb — wb.py 冒烟测试：起一个模拟工作台，验证命令、判据与退出码。

不依赖真实工作台。契约语义以 wb-base/SKILL.md 为准（usable 判定、in_use 不阻塞、
409 非缺陷、失败归因四步、幂等键 md5 派生）。
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

WB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wb.py")

GOOD_PORT = {
    "id": "sta-main", "enabled": True, "workbench_ready": True, "errors": [],
    "checks": {"open_ok": True, "in_use": False}, "usable": True,
}
BAD_PORT = {
    "id": "bad-port", "enabled": True, "workbench_ready": False,
    "errors": ["windows 双通道断开"], "checks": {"open_ok": False, "in_use": False},
    "usable": False,
}
BUSY_PORT = {
    "id": "busy-port", "enabled": True, "workbench_ready": True, "errors": [],
    "checks": {"open_ok": None, "in_use": True}, "usable": True,
}

FLASH_BODIES = []  # 记录 flash-jobs 提交体，验证幂等键
STOPS = []         # 记录 stop 请求体（验证 force 兜底）
JOB_POLLS = {}     # job_id -> GET 次数（模拟异步）
FLASH_JOBS = {}    # client_request_id -> {job_id, session_id}（模拟服务端幂等注册表）


class MockWorkbench(BaseHTTPRequestHandler):
    def log_message(self, *a):  # 静默
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/api/health"):
            return self._json(200, {"status": "ok", "app": "workbench"})
        # 8766 v2.0.0：响应包一层 data（wb.py 需解包）
        if self.path.startswith("/host8766/api/v1/ports"):  # 占位：真机由宿主直连，CLI 单测不覆盖
            return self._json(200, {"ok": True, "data": {"ports": []}})
        if self.path.startswith("/api/ai/v1/audit"):
            if not self.headers.get("Authorization"):
                return self._json(401, {"detail": "缺少 Bearer token"})
            last_bin = FLASH_BODIES[-1]["bin_path"] if FLASH_BODIES else ""
            return self._json(200, {"entries": [
                {"action": "flash.authorization", "operation_id": "op-audit1",
                 "result": json.dumps({"bin_path": last_bin, "authorization_source": "local_full_env"})}]})
        if self.path.startswith("/api/ai/v2/jobs?"):
            return self._json(200, {"jobs": [
                {"job_id": v["job_id"], "kind": "flash_job", "client_request_id": k,
                 "state": "succeeded" if v["job_id"] == "job-run" else "failed"}
                for k, v in FLASH_JOBS.items()], "count": len(FLASH_JOBS)})
        if self.path.startswith("/api/ai/v2/jobs/job-run"):
            JOB_POLLS["job-run"] = JOB_POLLS.get("job-run", 0) + 1
            if JOB_POLLS["job-run"] >= 3:
                return self._json(200, {"job_id": "job-run", "job_state": "succeeded",
                                        "summary": "flash_job succeeded"})
            return self._json(200, {"job_id": "job-run", "job_state": "running"})
        if self.path.startswith("/api/ai/v2/jobs/job-failrun"):
            return self._json(200, {
                "job_id": "job-failrun", "job_state": "failed",
                "summary": "烧录失败：Bootloader prompt was not detected.",
                "result": {"error": "Bootloader prompt was not detected."},
                "underlying_refs": ["op-xyz"]})
        if self.path.startswith("/api/ai/v2/jobs/job-ok"):
            return self._json(200, {"job_id": "job-ok", "job_state": "succeeded",
                                    "summary": "flash_job succeeded"})
        if self.path.startswith("/api/ai/v2/jobs/job-fail"):
            return self._json(200, {
                "job_id": "job-fail", "job_state": "failed",
                "summary": "flash_job error",
                "result": {"result": {"steps": [
                    {"name": "s1", "result": "fail",
                     "reason": "Bootloader prompt was not detected", "sent_hex": ""}]}},
                "underlying_refs": ["op-xyz"]})
        if "/evidence" in self.path:
            return self._json(200, {"level": "L1", "items": []})
        return self._json(404, {"detail": "no route " + self.path})

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if self.path.startswith("/api/serial-bridge/verify"):
            ports = []
            for pid in body.get("ports", []):
                m = {"sta-main": GOOD_PORT, "bad-port": BAD_PORT, "busy-port": BUSY_PORT}
                ports.append(m.get(pid, {"id": pid, "errors": ["unknown port"], "usable": False}))
            return self._json(200, {"ports": ports})
        if self.path.startswith("/api/ai/v2/module-actions"):
            if body.get("action") == "stop":
                if body.get("force"):
                    return self._json(200, {"job_state": "succeeded"})
                return self._json(409, {"code": "409", "message": "会话仍有活动观察任务，不能停止"})
            if body.get("mapping_id") == "bad-port":
                return self._json(409, {"code": 409, "message": "串口占用"})
            return self._json(200, {"job_state": "succeeded",
                                    "result": {"result": {"session_id": "ms-test123"}}})
        if self.path.startswith("/api/ai/v2/flash-jobs"):
            FLASH_BODIES.append(body)
            k = body.get("client_request_id")
            stored = FLASH_JOBS.get(k)
            if stored and stored.get("session_id") != body.get("session_id"):
                return self._json(409, {"code": "409", "message": "幂等键与既有请求不一致"})
            jid = "job-failrun" if "fail" in body.get("bin_path", "") else "job-run"
            FLASH_JOBS.setdefault(k, {"job_id": jid, "session_id": body.get("session_id")})
            return self._json(202, {"job_state": "running", "job_id": jid, "verdict": None})
        if self.path.startswith("/api/ai/v1/admin/grants"):
            if self.headers.get("X-Workbench-Admin-Key") != "test-key":
                return self._json(403, {"detail": "admin key 错"})
            return self._json(200, {"grant": {"grant_id": "g1", "scopes": body.get("scopes"),
                                              "firmware_roots": body.get("firmware_roots")},
                                    "token": "tok-secret-once"})
        return self._json(404, {"detail": "no route " + self.path})


class TestWb(unittest.TestCase):
    proc = None

    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), MockWorkbench)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.tmp = tempfile.mkdtemp()
        ops_dir = os.path.join(cls.tmp, "apps", "workbench", "runtime", "ai-control")
        os.makedirs(ops_dir)
        with open(os.path.join(ops_dir, "operations.json"), "w") as f:
            json.dump([{"operation_id": "op-xyz", "error": "serial open failed: device absent"}], f)
        cls.bin = os.path.join(cls.tmp, "iap_sta_venus2m_hv0101_sv001401_date260509_FC_F8_isv090007_idate261111.bin")
        open(cls.bin, "wb").write(os.urandom(1024))
        cls.failbin = os.path.join(cls.tmp, "iap_sta_fail_idate261111.bin")
        open(cls.failbin, "wb").write(os.urandom(1024))
        # 会话日志（含 BURN SUCCESS + 包数 + 烧后横幅），供 run 判定
        logdir = os.path.join(cls.tmp, "data", "logs", "模块", "sta")
        os.makedirs(logdir, exist_ok=True)
        cls.log = os.path.join(logdir, "20261118-103504_[sta]_[sta-main-COM18--run-hplc-serial-sta-main].log")
        open(cls.log, "w", encoding="utf-8").write(
            "[EVENT] 串口会话打开 session_id=ms-x mapping_id=sta-main\n"
            "[EVENT] XMODEM progress packet=1/2 bytes=1024/2048 pct=50\n"
            "[EVENT] XMODEM progress packet=2/2 bytes=2048/2048 pct=100\n"
            "[EVENT] 烧录完成：BURN SUCCESS\n"
            "[EVENT] RX text: 'Unicorn Bootloader\r\n boot_ver:ver_02-00-57\r\n sdk_ver:ver_03-00-03-11\r\n"
            " hver:0101, sver:001401\r\n isv :090007\r\n isv date:2026-11-11'\n")
        cls.latest = os.path.join(cls.tmp, "latest_flash.json")
        json.dump({"repo": cls.tmp, "target": "sta_venus2m",
                   "artifacts": [{"variant": "baseline", "bin_path": cls.bin}],
                   "latest": {"variant": "baseline", "bin_path": cls.bin}}, open(cls.latest, "w"))

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        FLASH_JOBS.clear()
        JOB_POLLS.clear()
        FLASH_BODIES.clear()

    def run_wb(self, *args, root=None, env_extra=None):
        env = dict(os.environ, WORKBENCH_BASE="http://127.0.0.1:%d" % self.port)
        if env_extra:
            env.update(env_extra)
        if root:
            env["WORKBENCH_ROOT"] = root
        p = subprocess.run([sys.executable, WB] + list(args), capture_output=True, text=True, env=env, timeout=60)
        return p

    def test_health(self):
        p = self.run_wb("health")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("✅", p.stdout)

    def test_preflight_good(self):
        p = self.run_wb("preflight", "sta-main")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("可过线", p.stdout)

    def test_preflight_bad(self):
        p = self.run_wb("preflight", "bad-port")
        self.assertEqual(p.returncode, 1)
        self.assertIn("不可过线", p.stdout)
        self.assertIn("windows 双通道断开", p.stdout)

    def test_preflight_busy_not_blocking(self):
        p = self.run_wb("preflight", "busy-port")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("in_use=true 不阻塞", p.stdout)

    def test_session_ensure(self):
        p = self.run_wb("session", "ensure", "sta", "--mapping", "sta-main")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("ms-test123", p.stdout)

    def test_session_409(self):
        p = self.run_wb("session", "ensure", "sta", "--mapping", "bad-port")
        self.assertEqual(p.returncode, 1)
        self.assertIn("409", p.stdout)

    def test_flash_run_success_e2e(self):
        p = self.run_wb("flash", "run", "--bin", self.bin, "--module", "sta",
                        "--mapping", "sta-main", "--timeout", "60", root=self.tmp,
                        env_extra={"WORKBENCH_AI_ADMIN_KEY": "test-key"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        j = json.loads(p.stdout.strip())
        self.assertEqual(j["verdict"], "flash_ok")
        self.assertEqual(j["banner"]["isv"], "090007")
        self.assertEqual(j["banner"]["isv_date"], "2026-11-11")
        cmpj = j["件名比对"]
        self.assertEqual(cmpj["可比数"], 4)
        self.assertEqual(cmpj["命中数"], 4)
        self.assertEqual([x["件名字段"] for x in cmpj["横幅无对应字段"]], ["260509", "FC_F8"])
        self.assertTrue(j["packet"]["全等"])
        self.assertEqual(j["audit"]["authorization_source"], "local_full_env")
        self.assertIn("README.md", os.listdir(j["evidence_dir"]))
        self.assertEqual(j["session_stop"], "ok")

    def test_flash_run_latest(self):
        p = self.run_wb("flash", "run", "--latest", self.tmp, "--module", "sta",
                        "--mapping", "sta-main", "--timeout", "60", root=self.tmp)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        j = json.loads(p.stdout.strip())
        self.assertEqual(j["bin"]["path"], self.bin)
        self.assertEqual(j["verdict"], "flash_ok")

    def test_flash_run_failure_attribution(self):
        p = self.run_wb("flash", "run", "--bin", self.failbin, "--module", "sta",
                        "--mapping", "sta-main", "--timeout", "60", root=self.tmp)
        self.assertEqual(p.returncode, 1)
        j = json.loads(p.stdout.strip())
        self.assertEqual(j["verdict"], "flash_failed")
        self.assertIn("attribution", j)
        self.assertIn("空行自证", j["hint"])

    def test_flash_run_rejects_non_iap(self):
        fake = os.path.join(self.tmp, "flash_prod.bin")
        open(fake, "wb").write(b"x" * 64)
        p = self.run_wb("flash", "run", "--bin", fake, root=self.tmp)
        self.assertEqual(p.returncode, 1)
        self.assertIn("rejected", json.loads(p.stdout.strip())["verdict"])

    def test_flash_run_replay_on_key_conflict(self):
        import hashlib
        key = "flash-%s-%s" % (os.path.basename(self.bin),
                               hashlib.md5(open(self.bin, "rb").read()).hexdigest()[:8])
        # 模拟此前已用另一会话烧过同件：同键绑定不同会话
        FLASH_JOBS[key] = {"job_id": "job-run", "session_id": "ms-other"}
        p = self.run_wb("flash", "run", "--bin", self.bin, "--module", "sta",
                        "--mapping", "sta-main", "--timeout", "60", root=self.tmp)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        j = json.loads(p.stdout.strip())
        self.assertEqual(j["verdict"], "flash_ok")
        self.assertTrue(j.get("idempotent_replay") or any(
            "回放" in s.get("note", "") for s in j.get("steps", [])))

    def test_session_stop_needs_force_on_409(self):
        p = self.run_wb("session", "stop", "ms-test123")
        self.assertEqual(p.returncode, 1)
        self.assertIn("--force", p.stdout)
        p2 = self.run_wb("session", "stop", "ms-test123", "--force")
        self.assertEqual(p2.returncode, 0, p2.stdout + p2.stderr)

    def test_flash_submit_idempotent_key(self):
        p1 = self.run_wb("flash", "submit", self.bin, "--session", "ms-test123")
        self.assertEqual(p1.returncode, 0, p1.stdout + p1.stderr)
        self.assertIn("job_id=job-run", p1.stdout)
        p2 = self.run_wb("flash", "submit", self.bin, "--session", "ms-test123")
        self.assertEqual(p2.returncode, 0)
        self.assertEqual(FLASH_BODIES[-2]["client_request_id"], FLASH_BODIES[-1]["client_request_id"],
                         "同件重提必须复用同一幂等键")
        self.assertIn("md5=", p1.stdout)

    def test_flash_rejects_non_iap(self):
        fake = os.path.join(self.tmp, "flash_prod.bin")
        open(fake, "wb").write(b"x" * 64)
        p = self.run_wb("flash", "submit", fake, "--session", "ms-test123")
        self.assertEqual(p.returncode, 2)
        self.assertIn("iap_", p.stderr)

    def test_wait_success(self):
        p = self.run_wb("wait", "job-ok")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("succeeded", p.stdout)
        self.assertIn("BURN SUCCESS", p.stdout)  # 成功也要提醒 verdict≠业务判定

    def test_wait_failure_attribution(self):
        p = self.run_wb("wait", "job-fail", root=self.tmp)
        self.assertEqual(p.returncode, 1)
        self.assertIn("① step[s1]", p.stdout)
        self.assertIn("根本没发出去", p.stdout)
        self.assertIn("④ operations.json", p.stdout)
        self.assertIn("serial open failed: device absent", p.stdout)
        self.assertIn("L1 证据 items:[]", p.stdout)

    def test_auth_token_masked_in_json(self):
        env = dict(os.environ, WORKBENCH_AI_ADMIN_KEY="test-key",
                   WORKBENCH_BASE="http://127.0.0.1:%d" % self.port)
        p = subprocess.run([sys.executable, WB, "auth", "--scopes", "module_flash:execute",
                            "--reason", "测试", "--json"],
                           capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertNotIn("tok-secret-once", p.stdout, "--json 也要遮蔽 token")

    def test_conn_refused(self):
        env = dict(os.environ, WORKBENCH_BASE="http://127.0.0.1:1")
        p = subprocess.run([sys.executable, WB, "health"], capture_output=True, text=True, env=env, timeout=30)
        self.assertEqual(p.returncode, 3, p.stdout + p.stderr)
        self.assertIn("工作台不在线", p.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
