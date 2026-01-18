"""Quick test - Run actual downloads"""
from terprint_menu_downloader import DispensaryOrchestrator

print("\n🧪 Running Quick Download Test\n")

orchestrator = DispensaryOrchestrator()

# Just run it - we'll kill after 2 minutes
print("Starting downloads (will stop after ~2 minutes)...")
results = orchestrator.run_full_pipeline()

print(f"\n✅ Results:")
print(f"   Successful: {results.get('successful', 0)}")
print(f"   Failed: {results.get('failed', 0)}")
