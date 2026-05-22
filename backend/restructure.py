#!/usr/bin/env python3
"""Execute backend restructuring - Enhanced version."""

import os
import sys
from pathlib import Path

# Ensure we're in the backend directory
backend_dir = Path(__file__).parent.resolve()
os.chdir(backend_dir)

print("🚀 Starting restructuring from:", backend_dir)

# Create app package structure
try:
    Path("app").mkdir(exist_ok=True)
    Path("app/config").mkdir(exist_ok=True)
    Path("app/scanner").mkdir(exist_ok=True)
    Path("app/fetcher").mkdir(exist_ok=True)
    Path("app/orchestrator").mkdir(exist_ok=True)
    Path("app/api").mkdir(exist_ok=True)
    Path("tests").mkdir(exist_ok=True)
    print("✓ Created all directories")
except Exception as e:
    print(f"✗ Failed to create directories: {e}")
    sys.exit(1)

# Move and convert files
moves = [
    ("config.py", "app/config/settings.py", []),
    ("scan.py", "app/scanner/scan.py", []),
    ("static_scanner.py", "app/scanner/static_scanner.py", [("from scan import", "from .scan import")]),
    ("fetcher.py", "app/fetcher/fetcher.py", [("from config import", "from ..config import"), ("from scan import", "from ..scanner import")]),
    ("orchestrator.py", "app/orchestrator/orchestrator.py", [("from fetcher import", "from ..fetcher import"), ("from static_scanner import", "from ..scanner import"), ("from scan import", "from ..scanner import")]),
    ("routes.py", "app/api/routes.py", [("from orchestrator import", "from ..orchestrator import"), ("from scan import", "from ..scanner import")]),
    ("main.py", "app/main.py", [("from routes import", "from .api import"), ("from config import", "from .config import")]),
    ("test_static_scanner.py", "tests/test_static_scanner.py", [("from static_scanner import", "from app.scanner import"), ("from scan import", "from app.scanner import")]),
]

for src, dst, replacements in moves:
    src_p = Path(src)
    if not src_p.exists():
        print(f"⚠ Skipping {src} (not found)")
        continue
    
    try:
        content = src_p.read_text()
        for old, new in replacements:
            content = content.replace(old, new)
        
        dst_p = Path(dst)
        dst_p.parent.mkdir(parents=True, exist_ok=True)
        dst_p.write_text(content)
        src_p.unlink()
        print(f"✓ {src} → {dst}")
    except Exception as e:
        print(f"✗ Failed to move {src}: {e}")

# Create __init__ files
inits = {
    "app/__init__.py": '"""RepoGuard backend application package."""\n\n__version__ = "0.1.0"\n',
    "app/config/__init__.py": '"""Configuration module."""\n\nfrom .settings import Settings, get_settings, settings\n\n__all__ = ["Settings", "get_settings", "settings"]\n',
    "app/scanner/__init__.py": '"""Scanner module."""\n\nfrom .static_scanner import StaticScanner, calculate_trust_score\nfrom .scan import ScanRequest, ScanResponse, ScanResult, PatternMatch, AccountInfo, TrustLevel\n\n__all__ = ["StaticScanner", "calculate_trust_score", "ScanRequest", "ScanResponse", "ScanResult", "PatternMatch", "AccountInfo", "TrustLevel"]\n',
    "app/fetcher/__init__.py": '"""Fetcher module."""\n\nfrom .fetcher import RepoFetcher\n\n__all__ = ["RepoFetcher"]\n',
    "app/orchestrator/__init__.py": '"""Orchestrator module."""\n\nfrom .orchestrator import ScanOrchestrator\n\n__all__ = ["ScanOrchestrator"]\n',
    "app/api/__init__.py": '"""API module."""\n\nfrom .routes import router\n\n__all__ = ["router"]\n',
    "tests/__init__.py": '"""Test module."""\n',
}

for init_path, init_content in inits.items():
    try:
        p = Path(init_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(init_content)
        print(f"✓ Created {init_path}")
    except Exception as e:
        print(f"✗ Failed to create {init_path}: {e}")

print("\n✅ Restructuring complete!")
