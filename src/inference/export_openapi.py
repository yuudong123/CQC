"""실제 모델을 읽지 않고 추론 API의 OpenAPI 계약 문서를 내보낸다."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .api import create_app


class _SchemaOnlyPredictor:
    views = 12

    def health(self) -> dict[str, Any]:
        raise RuntimeError("schema-only predictor")

    def predict(self, images: list[bytes]) -> Any:
        raise RuntimeError("schema-only predictor")


def main(argv: list[str] | None = None) -> int:
    """실행 인자를 읽고 다음 작업을 수행한다: 실제 모델을 읽지 않고 추론 API의 OpenAPI 계약 문서를 내보낸다."""
    parser = argparse.ArgumentParser(description="inference OpenAPI JSON 생성")
    parser.add_argument(
        "--output", type=Path, default=Path("docs/contracts/inference-openapi.json")
    )
    args = parser.parse_args(argv)
    schema = create_app(_SchemaOnlyPredictor()).openapi()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"openapi={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
