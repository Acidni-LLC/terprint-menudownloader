from terprint_menu_downloader.genetics.storage import GeneticsStorage
import asyncio

storage = GeneticsStorage()
index = asyncio.run(storage.load_index())

print(f'\nTotal strains in genetics database: {len(index)}')
print(f'\nSample (first 20):')
for i, strain in enumerate(list(index.values())[:20]):
    print(f'  {strain["strain_name"]}: {strain["parent_1"]} x {strain["parent_2"]}')
