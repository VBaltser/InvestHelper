"""Test the built nginx/backend pair without external API credentials."""
import json
import re
import sys
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

BASE_URL = ""


def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE_URL + path, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        response = urllib.request.urlopen(req, timeout=10)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return response.status, response.headers, response.read()


class BuiltApplicationTests(unittest.TestCase):
    def test_backend_health_through_nginx(self):
        status, _, body = request("/api/health")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"status": "ok"})

    def test_frontend_serves_built_assets(self):
        status, headers, body = request("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        html = body.decode()
        self.assertIn('id="root"', html)
        assets = re.findall(r'(?:src|href)="(/assets/[^" ]+)"', html)
        self.assertTrue(assets, "No compiled frontend assets in index.html")
        self.assertTrue(any(asset.endswith(".js") for asset in assets))
        for asset in assets:
            with self.subTest(asset=asset):
                status, headers, content = request(asset)
                self.assertEqual(status, 200)
                self.assertTrue(content)
                self.assertNotIn("text/html", headers.get("Content-Type", ""))

    def test_spa_navigation(self):
        status, _, body = request("/portfolio/ci-test-account")
        self.assertEqual(status, 200)
        self.assertIn(b'id="root"', body)

    def test_invalid_screener_page_rejected(self):
        status, _, body = request("/api/bonds/screener?page=0")
        self.assertEqual(status, 422)
        self.assertTrue(any("page" in item["loc"] for item in json.loads(body)["detail"]))

    def test_invalid_chat_request_rejected(self):
        status, _, body = request("/api/chat", {})
        self.assertEqual(status, 422)
        self.assertIn("detail", json.loads(body))


class JUnitResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cases = []

    def startTest(self, test):
        self.started = time.monotonic()
        self.case = ET.Element("testcase", name=test.id(), classname=type(test).__name__)
        self.cases.append(self.case)
        super().startTest(test)

    def stopTest(self, test):
        self.case.set("time", str(time.monotonic() - self.started))
        super().stopTest(test)

    def addFailure(self, test, err):
        ET.SubElement(self.case, "failure").text = self._exc_info_to_string(err, test)
        super().addFailure(test, err)

    def addError(self, test, err):
        ET.SubElement(self.case, "error").text = self._exc_info_to_string(err, test)
        super().addError(test, err)

    def addSubTest(self, test, subtest, err):
        if err is not None:
            ET.SubElement(self.case, "failure").text = self._exc_info_to_string(err, test)
        super().addSubTest(test, subtest, err)


if __name__ == "__main__":
    BASE_URL = sys.argv[1].rstrip("/")
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BuiltApplicationTests)
    result = unittest.TextTestRunner(verbosity=2, resultclass=JUnitResult).run(suite)
    xml = ET.Element("testsuite", name="BuiltApplication", tests=str(result.testsRun),
                     failures=str(len(result.failures)), errors=str(len(result.errors)))
    xml.extend(result.cases)
    output = Path(sys.argv[2])
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(xml).write(output, encoding="utf-8", xml_declaration=True)
    sys.exit(0 if result.wasSuccessful() else 1)
