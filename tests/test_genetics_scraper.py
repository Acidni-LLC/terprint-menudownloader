import sys
from pathlib import Path

# Ensure src/ is on sys.path for local test runs
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from terprint_menu_downloader.genetics.scraper import GeneticsScraper


def test_curaleaf_lineage_parsing():
    scraper = GeneticsScraper()
    product = {
        "name": "Blue Dream - Flower",
        "strain": "Blue Dream",
        "description": "Lineage: Blueberry x Haze"
    }
    res = scraper.extract_from_menu({"products": [product]}, dispensary="curaleaf")
    assert res.unique_strains == 1
    g = res.genetics_found[0]
    assert g.strain_name == "Blue Dream"
    assert g.parent_1 == "Blueberry"
    assert g.parent_2 == "Haze"


def test_generic_lineage_variations():
    scraper = GeneticsScraper()
    product = {
        "name": "Blue Dream - Flower",
        "strain": "Blue Dream",
        "description": "Parents - Blueberry X Haze"
    }
    res = scraper.extract_from_menu({"products": [product]}, dispensary="unknown")
    assert res.unique_strains == 1
    g = res.genetics_found[0]
    assert g.parent_1 == "Blueberry"
    assert g.parent_2 == "Haze"


def test_cookies_informations_genetics():
    scraper = GeneticsScraper()
    product = {
        "name": "Blue Dream - Flower",
        "informations": {"genetics": "Blueberry x Haze"}
    }
    res = scraper.extract_from_menu({"products": [product]}, dispensary="cookies")
    assert res.unique_strains == 1
    g = res.genetics_found[0]
    assert g.parent_1 == "Blueberry"
    assert g.parent_2 == "Haze"