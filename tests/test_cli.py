"""Testes da CLI oficial do Nexus."""

from nexus.cli import main


def test_version_command(capsys):
    exit_code = main(["version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out.strip() == "Nexus Runtime Platform v2300.0.0-dev"
