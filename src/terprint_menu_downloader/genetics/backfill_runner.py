"""
Batch runner to backfill genetics in small, date-scoped slices.

Usage examples:
  # Last 2 months for trulieve, 150 blobs per slice
  python -m terprint_menu_downloader.genetics.backfill_runner --dispensary trulieve --months 2 --max 150 --save

  # Specific year-month range for cookies, 100 blobs per slice
  python -m terprint_menu_downloader.genetics.backfill_runner --dispensary cookies --start 2025-11 --end 2026-01 --max 100 --save

Environment (optional):
  MENUS_STORAGE_ACCOUNT   default: stterprintsharedgen2
  MENUS_CONTAINER         default: jsonfiles
  AZURE_STORAGE_CONNECTION_STRING (preferred if available)
"""

import argparse
from datetime import datetime
from typing import List, Tuple

from .backfill import run_backfill


def month_sequence(start: str = None, end: str = None, months: int = None) -> List[Tuple[int, int]]:
    """Return list of (year, month) tuples.
    - If months is provided, include that many recent months (including current month).
    - If start/end are provided (YYYY-MM), generate inclusive range.
    """
    today = datetime.utcnow()
    if months:
        seq = []
        y, m = today.year, today.month
        for _ in range(months):
            seq.append((y, m))
            m -= 1
            if m == 0:
                m = 12
                y -= 1
        return list(reversed(seq))

    if start and end:
        sy, sm = map(int, start.split("-"))
        ey, em = map(int, end.split("-"))
        seq = []
        y, m = sy, sm
        while (y < ey) or (y == ey and m <= em):
            seq.append((y, m))
            m += 1
            if m == 13:
                m = 1
                y += 1
        return seq

    # Default: just current month
    return [(today.year, today.month)]


def main():
    parser = argparse.ArgumentParser(description="Batch runner for genetics backfill in date slices")
    parser.add_argument("--dispensary", required=True, help="Dispensary id (e.g., trulieve, cookies, curaleaf, muv, flowery, sunburn)")
    parser.add_argument("--months", type=int, help="Process the last N months (inclusive of current)")
    parser.add_argument("--start", help="Start month YYYY-MM")
    parser.add_argument("--end", help="End month YYYY-MM")
    parser.add_argument("--max", dest="max_items", type=int, default=150, help="Max blobs per slice")
    parser.add_argument("--save", action="store_true", help="Persist genetics and refresh index per slice")
    parser.add_argument("--enable-scraping", action="store_true", help="Enable product page scraping for Cookies/Flowery/Curaleaf (slower but finds more genetics)")
    args = parser.parse_args()

    slices = month_sequence(start=args.start, end=args.end, months=args.months)
    if not slices:
        print("No slices to process")
        return 0

    print(f"[INFO] Processing {len(slices)} slice(s) for {args.dispensary}, max {args.max_items} blobs each")
    if args.enable_scraping:
        print("[INFO] Product page scraping ENABLED - this will be slower but extract more genetics")

    for y, m in slices:
        prefix = f"dispensaries/{args.dispensary}/{y:04d}/{m:02d}/"
        print(f"\n[SLICE] {y:04d}-{m:02d} prefix={prefix}")
        run_backfill(
            dispensary=args.dispensary,
            max_items=args.max_items,
            save=args.save,
            prefix=prefix,
            enable_scraping=args.enable_scraping,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())