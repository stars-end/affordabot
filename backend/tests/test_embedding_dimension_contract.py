from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
OWNED_FILES = [
    "main.py",
    "scripts/substrate/manual_capture.py",
    "scripts/cron/run_daily_scrape.py",
    "scripts/cron/run_rag_spiders.py",
]


def _read(relative_path: str) -> str:
    return (BACKEND_ROOT / relative_path).read_text(encoding="utf-8")


def test_owned_retrieval_paths_no_longer_reference_1536():
    for relative_path in OWNED_FILES:
        assert "1536" not in _read(relative_path), relative_path


def test_owned_retrieval_paths_share_4096_contract_constant():
    for relative_path in OWNED_FILES:
        content = _read(relative_path)
        assert "EMBEDDING_DIMENSIONS = 4096" in content, relative_path
        assert "dimensions=EMBEDDING_DIMENSIONS" in content, relative_path
