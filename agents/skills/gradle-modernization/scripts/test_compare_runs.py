import tempfile
import unittest
from pathlib import Path

from compare_runs import compare, summarize

LOG = """> Task :app:compileJava
> Task :app:test
> Task :app:integrationTest {integration}
> Task :lib:jar UP-TO-DATE
{cache}
BUILD SUCCESSFUL in 3s
"""

XML = """<testsuite name="ATest" tests="{n}"><testcase classname="ATest" name="one"/>{extra}</testsuite>"""


def write_run(root: Path, label: str, integration="", cache="", extra="", n=1):
    log = root / f"{label}.log"
    log.write_text(LOG.format(integration=integration, cache=cache))
    xml_dir = root / label / "xml"
    xml_dir.mkdir(parents=True)
    (xml_dir / "TEST-ATest.xml").write_text(XML.format(n=n, extra=extra))
    return summarize(log, {":app:test": xml_dir})


class CompareRuns(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix=".compare-runs-test-", dir=Path.cwd())
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_identical_runs_are_ok(self):
        a, b = write_run(self.root, "a"), write_run(self.root, "b")
        self.assertEqual(a["tasks"][":lib:jar"], "UP-TO-DATE")
        self.assertEqual(a["tests"][":app:test"]["counts"], {"passed": 1})
        self.assertTrue(compare(a, b)["ok"])

    def test_task_outcome_change_and_no_source_are_reported(self):
        a, b = write_run(self.root, "a"), write_run(self.root, "b", integration="NO-SOURCE")
        result = compare(a, b)
        self.assertFalse(result["ok"])
        self.assertIn(":app:integrationTest", result["problems"][0])
        self.assertTrue(compare(a, b, ignore_tasks={":app:integrationTest"})["ok"])

    def test_test_identity_change_is_reported(self):
        a = write_run(self.root, "a")
        b = write_run(self.root, "b", extra='<testcase classname="ATest" name="two"><failure/></testcase>', n=2)
        result = compare(a, b)
        self.assertFalse(result["ok"])
        self.assertTrue(any("identities" in p for p in result["problems"]))

    def test_cache_pair_requires_store_then_reuse(self):
        a = write_run(self.root, "a", cache="Configuration cache entry stored.")
        b = write_run(self.root, "b", cache="Reusing configuration cache.")
        self.assertTrue(compare(a, b, cache_pair=True)["ok"])
        self.assertFalse(compare(b, a, cache_pair=True)["ok"])


if __name__ == "__main__":
    unittest.main()
