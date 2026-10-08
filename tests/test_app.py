"""核心业务集成测试：临时数据库，不影响日常签到记录。"""

import csv
import io
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, get_db  # noqa: E402


class AttendanceTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.config = {
            "TESTING": True,
            "SECRET_KEY": "test-secret-only",
            "DATABASE": str(Path(self.directory.name) / "test.db"),
        }
        self.app = create_app(self.config)
        self.teacher = self.app.test_client()
        self.student = self.app.test_client()

    def tearDown(self):
        self.directory.cleanup()

    def post(self, client, path, values, token_page="/"):
        client.get(token_page)
        with client.session_transaction() as state:
            token = state["csrf_token"]
        return client.post(path, data={**values, "csrf_token": token})

    def login(self):
        response = self.post(self.teacher, "/teacher/login", {
            "username": "admin", "password": "admin123",
        }, "/teacher/login")
        self.assertEqual(response.status_code, 302)

    def create_session(self, course="软件工程", title="实验一签到"):
        response = self.post(self.teacher, "/teacher/create", {
            "course_name": course, "title": title, "duration": "10",
        }, "/teacher")
        self.assertEqual(response.status_code, 302)
        session_id = int(response.location.rsplit("/", 1)[-1])
        with self.app.app_context():
            return dict(get_db().execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())

    def checkin(self, item, client=None, student_id="20240001", name="测试同学"):
        return self.post(client or self.student, "/", {
            "code": item["code"], "student_id": student_id, "name": name,
        })

    def test_complete_flow_and_csv(self):
        self.login()
        item = self.create_session()
        response = self.checkin(item)
        self.assertEqual(response.status_code, 302)
        receipt = self.student.get("/success").get_data(as_text=True)
        self.assertIn("签到成功", receipt)
        self.assertIn("测试同学", receipt)
        self.assertIn("软件工程", receipt)
        detail = self.teacher.get(f'/teacher/sessions/{item["id"]}').get_data(as_text=True)
        self.assertIn("20240001", detail)
        export = self.teacher.get(f'/teacher/sessions/{item["id"]}/export')
        self.assertEqual(export.status_code, 200)
        self.assertTrue(export.data.startswith(b"\xef\xbb\xbf"))
        rows = list(csv.reader(io.StringIO(export.data.decode("utf-8-sig"))))
        self.assertEqual(rows[1][1:5], ["20240001", "测试同学", "软件工程", "实验一签到"])

    def test_duplicate_is_rejected_even_with_different_name(self):
        self.login()
        item = self.create_session()
        self.assertEqual(self.checkin(item).status_code, 302)
        duplicate = self.checkin(item, self.app.test_client(), name="另一个名字")
        self.assertEqual(duplicate.status_code, 409)
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)
            self.assertEqual(get_db().execute("SELECT name FROM attendance").fetchone()[0], "测试同学")
        other = self.create_session(title="第二次签到")
        self.assertEqual(self.checkin(other).status_code, 302)

    def test_concurrent_duplicate_only_writes_once(self):
        self.login()
        item = self.create_session()
        clients = [self.app.test_client(), self.app.test_client()]
        for client in clients:
            client.get("/")
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda c: self.checkin(item, c).status_code, clients))
        self.assertEqual(sorted(results), [302, 409])
        with self.app.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)

    def test_expiration_and_manual_close(self):
        self.login()
        item = self.create_session()
        with patch("app.time.time", return_value=item["ends_at"]):
            self.assertEqual(self.checkin(item).status_code, 410)
        response = self.post(self.teacher, f'/teacher/sessions/{item["id"]}/close', {}, "/teacher")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.checkin(item).status_code, 410)

    def test_authentication_and_csrf(self):
        for path in ["/teacher", "/teacher/sessions/1", "/teacher/sessions/1/export"]:
            response = self.student.get(path)
            self.assertEqual(response.status_code, 302)
            self.assertIn("/teacher/login", response.location)
        self.assertEqual(self.student.post("/", data={"code": "123456"}).status_code, 400)
        self.assertEqual(self.student.post("/", data={"csrf_token": "无效令牌"}).status_code, 400)
        response = self.post(self.teacher, "/teacher/login", {
            "username": "admin", "password": "wrong-password",
        }, "/teacher/login")
        self.assertEqual(response.status_code, 401)
        with self.teacher.session_transaction() as state:
            self.assertNotIn("teacher_id", state)

    def test_invalid_input_and_leading_zero_code(self):
        self.login()
        with patch("app.secrets.randbelow", return_value=12345):
            item = self.create_session()
        self.assertEqual(item["code"], "012345")
        self.assertEqual(self.checkin(item, student_id="abc").status_code, 400)
        self.assertEqual(self.checkin(item, name=" ").status_code, 400)
        self.assertEqual(self.checkin({"code": "999999"}).status_code, 404)
        self.assertEqual(self.checkin(item).status_code, 302)

    def test_escape_html_and_csv_formula(self):
        self.login()
        item = self.create_session(course="=1+2")
        self.checkin(item, name="<script>alert(1)</script>")
        page = self.teacher.get(f'/teacher/sessions/{item["id"]}').get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        export = self.teacher.get(f'/teacher/sessions/{item["id"]}/export')
        rows = list(csv.reader(io.StringIO(export.data.decode("utf-8-sig"))))
        self.assertEqual(rows[1][3], "'=1+2")

    def test_records_survive_restart(self):
        self.login()
        item = self.create_session()
        self.checkin(item)
        restarted = create_app(self.config)
        with restarted.app_context():
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)
            self.assertEqual(get_db().execute("SELECT COUNT(*) FROM teachers").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
