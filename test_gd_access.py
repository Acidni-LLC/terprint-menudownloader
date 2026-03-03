#!/usr/bin/env python3
from terprint_menu_downloader.orchestrator import DispensaryOrchestrator

o = DispensaryOrchestrator()
keys = list(o.downloaders.keys())
print(f'All downloader keys: {keys}')

gd = o.downloaders.get('green_dragon')
print(f'Green Dragon found: {gd is not None}')
print(f'Green Dragon type: {type(gd).__name__ if gd else "None"}')

if gd:
    print(f'Has download method: {hasattr(gd, "download")}')
    print(f'Stores: {len(gd.stores) if hasattr(gd, "stores") else "N/A"}')
