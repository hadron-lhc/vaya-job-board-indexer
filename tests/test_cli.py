from __future__ import annotations

from pathlib import Path

from job_indexer.cli import main


CONFIG = Path(__file__).parents[1] / "config" / "sources.json"


def test_list_sources_prints_configured_sources(capsys) -> None:
    exit_code = main(["list-sources", "--config", str(CONFIG)])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "greenhouse-stripe" in output
    assert "greenhouse-airbnb" in output
    assert "lever-palantir" in output
    assert "lever-spotify" in output


def test_unknown_source_is_rejected(capsys) -> None:
    exit_code = main(
        [
            "fetch",
            "--platform",
            "greenhouse",
            "--source",
            "does-not-exist",
            "--config",
            str(CONFIG),
        ]
    )
    error = capsys.readouterr().err

    assert exit_code == 1
    assert "not configured" in error
