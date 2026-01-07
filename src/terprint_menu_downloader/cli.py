"""
CLI entry point for terprint-menu-downloader
"""
import sys

def main():
    """Main entry point - delegates to orchestrator's main function"""
    from .orchestrator import main as orchestrator_main
    orchestrator_main()

if __name__ == "__main__":
    main()
