from __future__ import annotations

from autosearch.core.secrets_store import load_secrets as load_runtime_secrets
from scripts.e2b.lib.secrets import load_secrets as load_e2b_secrets


def test_e2b_secrets_parser_matches_runtime_parser(tmp_path) -> None:
    secrets_file = tmp_path / "ai-secrets.env"
    secrets_file.write_text(
        "\n".join(
            [
                "XHS_COOKIES='a=b; c=d'",
                "ANTHROPIC_API_KEY='sk-ant-test-value'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert load_e2b_secrets(secrets_file) == load_runtime_secrets(secrets_file)
    assert load_e2b_secrets(secrets_file)["XHS_COOKIES"] == "a=b; c=d"
