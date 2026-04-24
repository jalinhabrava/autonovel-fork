#!/usr/bin/env python3
"""Legacy AutoNovel orchestrator wrapper.

This wrapper is kept for the classic AutoNovel novel-writing pipeline.
It is not the active TextifAI bootstrap/ingestion entrypoint.
"""

from scripts.pipeline.run_pipeline import main

if __name__ == "__main__":
    raise SystemExit(main())
