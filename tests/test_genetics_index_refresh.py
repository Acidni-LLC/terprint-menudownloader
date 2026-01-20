import json
from pathlib import Path
import tempfile

from terprint_menu_downloader.genetics.storage import GeneticsStorage


def write_partition(dir_path: Path, key: str, strains: list):
    part_dir = dir_path / "partitions"
    part_dir.mkdir(parents=True, exist_ok=True)
    content = {"strains": strains, "updated_at": "2026-01-19T00:00:00Z"}
    with (part_dir / f"{key}.json").open("w", encoding="utf-8") as f:
        json.dump(content, f)


def read_index(dir_path: Path):
    idx = dir_path / "index" / "strains-index.json"
    with idx.open("r", encoding="utf-8") as f:
        return json.load(f)


def test_refresh_index_builds_lookup_from_partitions():
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        # Create partitions with sample strains
        write_partition(
            base,
            "b",
            [
                {
                    "strain_name": "Blue Dream",
                    "strain_slug": "blue-dream",
                    "parent_1": "Blueberry",
                    "parent_2": "Haze",
                }
            ],
        )
        write_partition(
            base,
            "o",
            [
                {
                    "strain_name": "OG Kush",
                    "strain_slug": "og-kush",
                    "parent_1": "Chemdawg",
                    "parent_2": "Hindu Kush",
                }
            ],
        )

        storage = GeneticsStorage(use_local_fallback=True, local_dir=str(base))
        # Refresh index from local partitions
        import asyncio

        asyncio.run(storage.refresh_index())

        idx = read_index(base)
        assert idx["total_strains"] == 2
        assert set(idx["partitions"]) == {"b", "o"}
        assert idx["strains"]["blue-dream"]["partition"] == "b"
        assert idx["strains"]["blue-dream"]["has_lineage"] is True
        assert idx["strains"]["og-kush"]["partition"] == "o"
        assert idx["strains"]["og-kush"]["has_lineage"] is True