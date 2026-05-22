# Backend Restructure Guide

This guide explains how to reorganize the backend from a flat structure to a modular structure using an `app/` folder.

## New Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI entry point
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py             # (from config.py)
│   ├── scanner/
│   │   ├── __init__.py
│   │   ├── scan.py                 # (models from scan.py)
│   │   └── static_scanner.py       # (from static_scanner.py)
│   ├── fetcher/
│   │   ├── __init__.py
│   │   └── fetcher.py              # (from fetcher.py)
│   ├── orchestrator/
│   │   ├── __init__.py
│   │   └── orchestrator.py         # (from orchestrator.py)
│   └── api/
│       ├── __init__.py
│       └── routes.py               # (from routes.py)
├── tests/
│   ├── __init__.py
│   └── test_static_scanner.py      # (from backend root)
├── requirements.txt
├── .env
└── .gitignore
```

## Files to Create/Move

### Step 1: Create Directories
Create these directories under `backend/`:
- `app/`
- `app/config/`
- `app/scanner/`
- `app/fetcher/`
- `app/orchestrator/`
- `app/api/`
- `tests/`

### Step 2: Create __init__.py Files

**app/__init__.py**
```python
"""RepoGuard backend application package."""

__version__ = "0.1.0"
```

**app/config/__init__.py**
```python
"""Configuration module for RepoGuard."""

from .settings import Settings, get_settings, settings

__all__ = ["Settings", "get_settings", "settings"]
```

**app/scanner/__init__.py**
```python
"""Scanner module for RepoGuard."""

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
```

**app/fetcher/__init__.py**
```python
"""Fetcher module for RepoGuard."""

from .fetcher import RepoFetcher

__all__ = ["RepoFetcher"]
```

**app/orchestrator/__init__.py**
```python
"""Orchestrator module for RepoGuard."""

from .orchestrator import ScanOrchestrator

__all__ = ["ScanOrchestrator"]
```

**app/api/__init__.py**
```python
"""API module for RepoGuard."""

from .routes import router

__all__ = ["router"]
```

**tests/__init__.py**
```python
"""Test module for RepoGuard."""
```

### Step 3: Move and Update Files

#### app/config/settings.py
Move `config.py` to `app/config/settings.py` (no changes needed)

#### app/scanner/scan.py
Move `scan.py` to `app/scanner/scan.py` (no changes needed)

#### app/scanner/static_scanner.py
Move `static_scanner.py` to `app/scanner/` and update imports:
```python
# OLD
from scan import PatternMatch

# NEW  
from .scan import PatternMatch
```

#### app/fetcher/fetcher.py
Move `fetcher.py` to `app/fetcher/` and update imports:
```python
# OLD
from config import get_settings
from scan import AccountInfo

# NEW
from ..config import get_settings
from ..scanner import AccountInfo
```

#### app/orchestrator/orchestrator.py
Move `orchestrator.py` to `app/orchestrator/` and update imports:
```python
# OLD
from fetcher import RepoFetcher
from static_scanner import StaticScanner, calculate_trust_score
from scan import ScanResult, ScanResponse, TrustLevel, PatternMatch

# NEW
from ..fetcher import RepoFetcher
from ..scanner import StaticScanner, calculate_trust_score, ScanResult, ScanResponse, TrustLevel, PatternMatch
```

#### app/api/routes.py
Move `routes.py` to `app/api/` and update imports:
```python
# OLD
from orchestrator import ScanOrchestrator
from scan import ScanRequest, ScanResponse

# NEW
from ..orchestrator import ScanOrchestrator
from ..scanner import ScanRequest, ScanResponse
```

#### app/main.py
Move `main.py` to `app/` and update imports:
```python
# OLD
from routes import router
from config import settings

# NEW
from .api import router
from .config import settings
```

#### tests/test_static_scanner.py
Move `test_static_scanner.py` to `tests/` and update imports:
```python
# OLD
from static_scanner import StaticScanner
from scan import PatternMatch

# NEW
from app.scanner import StaticScanner, PatternMatch
```

### Step 4: Update Entry Point (if needed)

If running with uvicorn, update the command:
```bash
# OLD
uvicorn main:app

# NEW
uvicorn app.main:app
```

## Validation Checklist

- [ ] All directories created
- [ ] All __init__.py files created
- [ ] All files moved to correct locations
- [ ] All imports updated with relative/absolute paths
- [ ] No circular imports
- [ ] Application starts: `python -m uvicorn app.main:app`
- [ ] Tests pass: `python -m pytest tests/`
- [ ] No old files left in backend root (except requirements.txt, .env, .gitignore)

## Common Issues

**Import errors after moving:**
- Use relative imports (`.` and `..`) within app modules
- Use absolute imports from tests (`from app.module import ...`)

**Circular imports:**
- Move models/shared types to a `common.py` or directly in the module using them
- Import only from submodules, not from parent __init__ if possible

**Tests not finding modules:**
- Run tests from backend root: `python -m pytest tests/`
- Or ensure backend/ is in PYTHONPATH

