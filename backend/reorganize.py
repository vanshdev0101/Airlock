#!/usr/bin/env python3
"""Script to reorganize backend file structure from flat to modular."""

import os
import shutil
from pathlib import Path

# Detect backend directory
BACKEND_DIR = Path(__file__).parent.resolve()

print(f"Working directory: {BACKEND_DIR}\n")

# Define the new directory structure to create
DIRECTORIES = [
    "app",
    "app/config",
    "app/scanner",
    "app/fetcher",
    "app/orchestrator",
    "app/api",
    "tests",
]

# Files to move and their new locations
# Format: (source_filename, destination_path_relative_to_backend)
FILES_TO_MOVE = [
    ("config.py", "app/config/settings.py"),
    ("scan.py", "app/scanner/scan.py"),
    ("static_scanner.py", "app/scanner/static_scanner.py"),
    ("fetcher.py", "app/fetcher/fetcher.py"),
    ("orchestrator.py", "app/orchestrator/orchestrator.py"),
    ("routes.py", "app/api/routes.py"),
    ("main.py", "app/main.py"),
    ("test_static_scanner.py", "tests/test_static_scanner.py"),
]

# Content for __init__.py files
INIT_FILES = {
    "app/__init__.py": '''"""RepoGuard backend application package."""

__version__ = "0.1.0"
''',
    "app/config/__init__.py": '''"""Configuration module for RepoGuard."""

from .settings import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
''',
    "app/scanner/__init__.py": '''"""Scanner module for RepoGuard."""

from .static_scanner import StaticScanner, calculate_trust_score
from .scan import ScanRequest, ScanResponse, ScanResult, PatternMatch, AccountInfo, TrustLevel

__all__ = [
    "StaticScanner",
    "calculate_trust_score",
    "ScanRequest",
    "ScanResponse",
    "ScanResult",
    "PatternMatch",
    "AccountInfo",
    "TrustLevel",
]
''',
    "app/fetcher/__init__.py": '''"""Fetcher module for RepoGuard."""

from .fetcher import RepoFetcher

__all__ = ["RepoFetcher"]
''',
    "app/orchestrator/__init__.py": '''"""Orchestrator module for RepoGuard."""

from .orchestrator import ScanOrchestrator

__all__ = ["ScanOrchestrator"]
''',
    "app/api/__init__.py": '''"""API module for RepoGuard."""

from .routes import router

__all__ = ["router"]
''',
    "tests/__init__.py": '''"""Test module for RepoGuard."""
''',
}


def create_directories():
    """Create all required directories."""
    print("📁 Creating directories...")
    for dir_name in DIRECTORIES:
        dir_path = BACKEND_DIR / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"   ✓ {dir_name}/")
    print()


def move_files():
    """Move files to their new locations with updated imports."""
    print("📦 Moving files...")
    
    for src_name, dst_path in FILES_TO_MOVE:
        src_path = BACKEND_DIR / src_name
        dst_full = BACKEND_DIR / dst_path
        
        if not src_path.exists():
            print(f"   ⚠ Source not found: {src_name}")
            continue
        
        # Ensure destination directory exists
        dst_full.parent.mkdir(parents=True, exist_ok=True)
        
        # Read and update imports based on file type
        with open(src_path, 'r') as f:
            content = f.read()
        
        # Apply import updates based on destination
        content = update_imports(dst_path, content)
        
        # Write to new location
        with open(dst_full, 'w') as f:
            f.write(content)
        
        # Remove old file
        src_path.unlink()
        print(f"   ✓ {src_name} → {dst_path}")
    print()


def update_imports(dst_path: str, content: str) -> str:
    """Update imports in file content based on its new location."""
    
    # Determine how many levels deep the file is
    depth = dst_path.count('/')
    
    # Routes: app/api/routes.py
    if dst_path == "app/api/routes.py":
        content = content.replace(
            "from orchestrator import",
            "from ..orchestrator import"
        )
        content = content.replace(
            "from scan import",
            "from ..scanner import"
        )
    
    # Orchestrator: app/orchestrator/orchestrator.py
    elif dst_path == "app/orchestrator/orchestrator.py":
        content = content.replace(
            "from fetcher import",
            "from ..fetcher import"
        )
        content = content.replace(
            "from static_scanner import",
            "from ..scanner import"
        )
        content = content.replace(
            "from scan import",
            "from ..scanner import"
        )
    
    # Fetcher: app/fetcher/fetcher.py
    elif dst_path == "app/fetcher/fetcher.py":
        content = content.replace(
            "from config import",
            "from ..config import"
        )
        content = content.replace(
            "from scan import",
            "from ..scanner import"
        )
    
    # Static Scanner: app/scanner/static_scanner.py
    elif dst_path == "app/scanner/static_scanner.py":
        content = content.replace(
            "from scan import",
            "from .scan import"
        )
    
    # Main: app/main.py
    elif dst_path == "app/main.py":
        content = content.replace(
            "from routes import",
            "from .api import"
        )
        content = content.replace(
            "from config import",
            "from .config import"
        )
    
    # Tests: tests/test_static_scanner.py
    elif dst_path == "tests/test_static_scanner.py":
        content = content.replace(
            "from static_scanner import",
            "from app.scanner import"
        )
        content = content.replace(
            "from scan import",
            "from app.scanner import"
        )
    
    return content


def create_init_files():
    """Create __init__.py files for all packages."""
    print("⚙️  Creating __init__.py files...")
    for init_path, init_content in INIT_FILES.items():
        file_path = BACKEND_DIR / init_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write(init_content)
        print(f"   ✓ {init_path}")
    print()


def main():
    """Run the reorganization process."""
    print("\n" + "="*60)
    print("🚀 RepoGuard Backend Restructuring")
    print("="*60 + "\n")
    
    try:
        create_directories()
        move_files()
        create_init_files()
        
        print("="*60)
        print("✅ Restructuring complete!")
        print("="*60)
        print("\n📝 Next steps:")
        print("   1. Run: python -m uvicorn app.main:app --reload")
        print("   2. Run tests: python -m pytest tests/")
        print("   3. Verify imports work correctly\n")
        
    except Exception as e:
        print(f"\n❌ Error during restructuring: {e}")
        print(f"   Stack trace: {type(e).__name__}")
        raise


if __name__ == "__main__":
    main()
