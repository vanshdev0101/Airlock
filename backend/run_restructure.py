#!/usr/bin/env python3
"""Standalone restructuring script - Safe to run multiple times"""

import os
import shutil
from pathlib import Path

def main():
    backend = Path(__file__).parent.resolve()
    os.chdir(backend)
    
    print("=" * 70)
    print("🚀 RepoGuard Backend Restructuring")
    print("=" * 70)
    print(f"Working in: {backend}\n")
    
    # 1. Create directories
    print("📁 Creating directories...")
    dirs = ["app", "app/config", "app/scanner", "app/fetcher", "app/orchestrator", "app/api", "tests"]
    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        print(f"   ✓ {d}/")
    
    # 2. Move and transform files
    print("\n📦 Moving and updating files...")
    
    file_moves = [
        ("config.py", "app/config/settings.py", []),
        ("scan.py", "app/scanner/scan.py", []),
        ("static_scanner.py", "app/scanner/static_scanner.py", [("from scan import", "from .scan import")]),
        ("fetcher.py", "app/fetcher/fetcher.py", [
            ("from config import", "from ..config import"),
            ("from scan import", "from ..scanner import"),
        ]),
        ("orchestrator.py", "app/orchestrator/orchestrator.py", [
            ("from fetcher import", "from ..fetcher import"),
            ("from static_scanner import", "from ..scanner import"),
            ("from scan import", "from ..scanner import"),
        ]),
        ("routes.py", "app/api/routes.py", [
            ("from orchestrator import", "from ..orchestrator import"),
            ("from scan import", "from ..scanner import"),
        ]),
        ("main.py", "app/main.py", [
            ("from routes import", "from .api import"),
            ("from config import", "from .config import"),
        ]),
        ("test_static_scanner.py", "tests/test_static_scanner.py", [
            ("from static_scanner import", "from app.scanner import"),
            ("from scan import", "from app.scanner import"),
        ]),
    ]
    
    for src_name, dst_path, replacements in file_moves:
        src = Path(src_name)
        if not src.exists():
            print(f"   ⚠ {src_name} not found, skipping")
            continue
        
        try:
            content = src.read_text(encoding='utf-8')
            
            for old, new in replacements:
                content = content.replace(old, new)
            
            dst = Path(dst_path)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding='utf-8')
            src.unlink()
            print(f"   ✓ {src_name} → {dst_path}")
        except Exception as e:
            print(f"   ✗ Error with {src_name}: {e}")
    
    # 3. Create __init__ files
    print("\n⚙️  Creating __init__.py files...")
    
    inits = {
        "app/__init__.py": '"""RepoGuard backend application package."""\n\n__version__ = "0.1.0"\n',
        "app/config/__init__.py": '"""Configuration module for RepoGuard."""\n\nfrom .settings import Settings, get_settings, settings\n\n__all__ = ["Settings", "get_settings", "settings"]\n',
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
        "app/fetcher/__init__.py": '"""Fetcher module for RepoGuard."""\n\nfrom .fetcher import RepoFetcher\n\n__all__ = ["RepoFetcher"]\n',
        "app/orchestrator/__init__.py": '"""Orchestrator module for RepoGuard."""\n\nfrom .orchestrator import ScanOrchestrator\n\n__all__ = ["ScanOrchestrator"]\n',
        "app/api/__init__.py": '"""API module for RepoGuard."""\n\nfrom .routes import router\n\n__all__ = ["router"]\n',
        "tests/__init__.py": '"""Test module for RepoGuard."""\n',
    }
    
    for init_path, init_content in inits.items():
        try:
            p = Path(init_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(init_content, encoding='utf-8')
            print(f"   ✓ {init_path}")
        except Exception as e:
            print(f"   ✗ Error creating {init_path}: {e}")
    
    print("\n" + "=" * 70)
    print("✅ Restructuring complete!")
    print("=" * 70)
    print("\n📝 Next steps:")
    print("   1. Test: python -m uvicorn app.main:app --reload")
    print("   2. Tests: python -m pytest tests/")
    print("   3. Cleanup: del *_new.py, del reorganize.py, del restructure.py\n")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
