from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from textifai.runtime_config import RuntimeEnvironment


@dataclass
class TextifAISession:
    base_dir: Path
    vault_path: Path
    backend: str
    provider: str | None
    writer_model: str | None
    mode: str = "normal"
    policy_name: str = "default"
    token_budget: int = 4000
    last_result: Any | None = None
    last_context_request: dict | None = None
    last_context_pack: dict | None = None
    last_context_debug: dict | None = None
    running: bool = True

    def remember(self, result, *, request: dict | None = None, debug: dict | None = None) -> None:
        self.last_result = result
        if request is not None:
            self.last_context_request = request
        if isinstance(result, dict) and result.get("type") == "context_pack":
            self.last_context_pack = result
        elif isinstance(result, dict) and result.get("type") == "consistency_report":
            self.last_context_pack = result.get("context_pack")
            if result.get("context_request"):
                self.last_context_request = dict(result["context_request"])
        if debug is not None:
            self.last_context_debug = debug


def create_session(env: RuntimeEnvironment) -> TextifAISession:
    vault_path = Path(env.vault_root).expanduser() if env.vault_root else env.base_dir
    return TextifAISession(
        base_dir=env.base_dir,
        vault_path=vault_path,
        backend=env.backend or "vault",
        provider=env.provider,
        writer_model=env.writer_model,
    )
