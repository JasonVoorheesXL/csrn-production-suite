# CSRN Production Suite

CSRN Production Suite is a proprietary broadcast production platform for scholastic athletics.

## Current Release
- Version: 1.13.0-alpha.8f — Player Identity Repair and Source Alignment
- Build: V1.13A8F-SOURCE-ALIGNMENT
- Integration branch: `develop-1.13`
- Gate 2 merged checkpoint: `ef9d4a5d11b7c0aa6535e501d0a6503907120f76`
- Active engineering gate: Gate 3 — reproducible environment and tests

## Windows Setup and Startup

CSRN uses CPython 3.13.14 and exact runtime/development dependency locks.

1. Install Python 3.13.14 with the Python Install Manager for Windows:
   `py install 3.13.14`.
2. Run `SETUP_CSRN_ENVIRONMENT.bat` once to create or synchronize `.venv`.
3. Run `RUN_CSRN_COMMAND_CENTER.bat` for normal operation.

Normal Command Center startup does not access the network, upgrade tools, or
install packages. If the lock changes, rerun the explicit setup launcher.

Developers use `SETUP_CSRN_DEVELOPMENT_ENVIRONMENT.bat`, then validate with:

```text
.venv\Scripts\python.exe tools\dev_workflow.py validate
```

Build a deterministic release package from Git-tracked files with:

```text
.venv\Scripts\python.exe tools\build_release_package.py
```

## Branch Strategy
- main
- develop-1.13
- recovery/*
- gate3/*
- feature/*
- hotfix/*
- release/*

`main` remains a historical baseline until the recovery branch completes the
documented release gates in `CSRN_PROJECT_BIBLE.md`.
