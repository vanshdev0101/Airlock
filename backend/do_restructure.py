#!/usr/bin/env python3
"""Execute backend restructuring with proper directory creation."""

import os
import sys
from pathlib import Path
import shutil

# Change to backend directory
backend_dir = Path(__file__).parent.resolve()
os.chdir(backend_dir)

print("=" * 60)
print("🚀 RepoGuard Backend Restructuring")
print("=" * 60)

# Step 1: Create all directories
print("\n📁 Creating directories...")
directories = [
    "app",
    "app/config",
    "app/scanner",
    "app/fetcher",
    "app/orchestrator",
    "app/api",
    "tests",
]

for dir_name in directories:
    path = Path(dir_name)
    path.mkdir(parents=True, exist_ok=True)
    print(f"   ✓ {dir_name}/")

# Step 2: Files to move with import updates
print("\n📦 Moving and updating files...")

file_moves = {
    "config.py": ("app/config/settings.py", []),
    "scan.py": ("app/scanner/scan.py", []),
    "static_scanner.py": ("app/scanner/static_scanner.py", [
        ("from scan import", "from .scan import"),
    ]),
    "fetcher.py": ("app/fetcher/fetcher.py", [
        ("from config import", "from ..config import"),
        ("from scan import", "from ..scanner import"),
    ]),
    "orchestrator.py": ("app/orchestrator/orchestrator.py", [
        ("from fetcher import", "from ..fetcher import"),
        ("from static_scanner import", "from ..scanner import"),
        ("from scan import", "from ..scanner import"),
    ]),
    "routes.py": ("app/api/routes.py", [
        ("from orchestrator import", "from ..orchestrator import"),
        ("from scan import", "from ..scanner import"),
    ]),
    "main.py": ("app/main.py", [
        ("from routes import", "from .api import"),
        ("from config import", "from .config import"),
    ]),
    "test_static_scanner.py": ("tests/test_static_scanner.py", [
        ("from static_scanner import", "from app.scanner import"),
        ("from scan import", "from app.scanner import"),
    ]),
}

for src_file, (dst_path, replacements) in file_moves.items():
    src = Path(src_file)
    if not src.exists():
        print(f"   ⚠ {src_file} not found")
        continue
    
    # Read file
    with open(src, 'r') as f:
        content = f.read()
    
    # Apply replacements
    for old, new in replacements:
        content = content.replace(old, new)
    
    # Write to destination
    dst = Path(dst_path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, 'w') as f:
        f.write(content)
    
    # Remove original
    src.unlink()
    print(f"   ✓ {src_file} → {dst_path}")

# Step 3: Create __init__.py files
print("\n⚙️  Creating __init__.py files...")

init_files = {
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

for init_path, init_content in init_files.items():
    path = Path(init_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(init_content)
    print(f"   ✓ {init_path}")

print("\n" + "=" * 60)
print("✅ Restructuring complete!")
print("=" * 60)
print("\n📝 Next steps:")
print("   1. python -m uvicorn app.main:app --reload")
print("   2. python -m pytest tests/")
print("   3. Delete old .py template files if needed\n")
