"""Test script - Download from 1 store per dispensary"""
from terprint_menu_downloader import DispensaryOrchestrator
from terprint_menu_downloader.storage import AzureDataLakeManager
import logging

logging.basicConfig(level=logging.INFO)

# Limited stores for testing
test_stores = {
    "muv": ["tallahassee"],
    "cookies": ["miami"],
    "flowery": ["orlando"],
    "curaleaf": ["cape-canaveral"]
}

print("\n Testing Menu Downloader Locally - 1 store per dispensary\n")

orchestrator = DispensaryOrchestrator()
results = orchestrator.run_full_pipeline(limited_stores=test_stores)

print(f"\n Test Results:")
print(f"   Successful: {results['successful']}")
print(f"   Failed: {results['failed']}")
print(f"   Total: {results['total']}")
