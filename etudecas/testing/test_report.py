import json

from etudecas.testing.report import main, summarize


def test_report_preserves_setup_errors_failures_skips_and_successes(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('''<testsuites><testsuite>
      <testcase classname="engine" name="ok"/>
      <testcase classname="engine" name="wrong"><failure message="assertion">trace</failure></testcase>
      <testcase classname="fixtures" name="setup"><error message="missing file">details</error></testcase>
      <testcase classname="historical" name="old"><skipped message="explicit opt-in"/></testcase>
    </testsuite></testsuites>''', encoding="utf-8")
    output = tmp_path / "summary.json"
    assert main(["--junit", str(source), "--output", str(output)]) == 1
    result = json.loads(output.read_text(encoding="utf-8"))
    assert result["counts"] == {"passed": 1, "failure": 1, "error": 1, "skipped": 1}
    assert result["failures"][0]["detail"] == "trace"
    assert result["failures"][1]["name"] == "setup"
    assert result["skip_reasons"] == {"explicit opt-in": 1}


def test_empty_or_invalid_report_is_not_success(tmp_path):
    source = tmp_path / "results.xml"
    for content in ("<broken", "<testsuite/>", "<other/>"):
        source.write_text(content, encoding="utf-8")
        assert main(["--junit", str(source), "--output", str(tmp_path / "report.json")]) == 2


def test_single_suite_and_parameterized_names_are_preserved(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('<testsuite><testcase classname="module.Class" name="test[a-b]"/></testsuite>', encoding="utf-8")
    assert summarize(source)["counts"] == {"passed": 1}
    assert main(["--junit", str(source), "--output", str(tmp_path / "report.json")]) == 0


def test_multiple_failure_diagnostics_are_not_lost(tmp_path):
    source = tmp_path / "results.xml"
    source.write_text('<testsuite><testcase name="subtests"><failure message="first"/>'
                      '<failure message="second"/></testcase></testsuite>', encoding="utf-8")
    result = summarize(source)
    assert result["counts"] == {"failure": 1}
    assert [row["message"] for row in result["failures"]] == ["first", "second"]
