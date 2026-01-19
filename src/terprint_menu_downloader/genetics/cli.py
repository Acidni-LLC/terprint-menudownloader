import argparse
import json
import os
from pathlib import Path
from typing import List, Dict

from .scraper import GeneticsScraper
from .storage import GeneticsStorage


def find_json_files(input_path: Path, recursive: bool) -> List[Path]:
    if input_path.is_file() and input_path.suffix.lower() == ".json":
        return [input_path]
    patterns = ["*.json"]
    files: List[Path] = []
    if recursive:
        for pattern in patterns:
            files.extend(input_path.rglob(pattern))
    else:
        for pattern in patterns:
            files.extend(input_path.glob(pattern))
    return files


def load_json(path: Path) -> Dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Extract strain genetics from menu JSON files.")
    parser.add_argument("--dispensary", required=True, help="Dispensary identifier (e.g., trulieve, cookies, curaleaf, muv, flowery)")
    parser.add_argument("--input", required=True, help="Path to a JSON file or a folder containing JSON files")
    parser.add_argument("--recursive", action="store_true", help="Recursively search for JSON files in subfolders")
    parser.add_argument("--save", action="store_true", help="Save extracted genetics to storage (Azure Blob or local fallback)")
    args = parser.parse_args()

    input_path = Path(args.input)
    files = find_json_files(input_path, args.recursive)
    if not files:
        print("No JSON files found.")
        return 1

    scraper = GeneticsScraper()
    all_genetics = []
    total_files = 0
    total_strains = 0

    for file_path in files:
        try:
            data = load_json(file_path)
            result = scraper.extract_from_menu(data, dispensary=args.dispensary, source_file=file_path.name)
            total_files += 1
            total_strains += result.unique_strains
            all_genetics.extend(result.genetics_found)
            print(f"[OK] {file_path.name}: {result.unique_strains} strains")
        except Exception as e:
            print(f"[WARN] {file_path}: {e}")

    print(f"\nSummary: {total_files} files, ~{total_strains} strains with genetics")

    if args.save and all_genetics:
        import asyncio

        async def _save():
            storage = GeneticsStorage()
            await storage.connect()
            stats = await storage.save_genetics(all_genetics)
            print(f"Saved: {stats['new']} new, {stats['updated']} updated")

        try:
            asyncio.run(_save())
        except RuntimeError:
            # Handle existing event loop (e.g., in certain environments)
            import asyncio as aio
            loop = aio.new_event_loop()
            aio.set_event_loop(loop)
            loop.run_until_complete(_save())
            loop.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())