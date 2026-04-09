#!/usr/bin/env python3
"""
Checkpoint manager for resumable health data ingestion.
Reads/writes checkpoint state so ingestion can resume after interruption.
"""

import os
import yaml
from pathlib import Path
from typing import Optional


class CheckpointManager:
    """Manages ingestion checkpoint state for resumable processing."""

    def __init__(self, state_dir: str):
        self.state_dir = Path(state_dir).expanduser()
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_file = self.state_dir / "checkpoint.yaml"

    def load(self) -> Optional[dict]:
        """Load checkpoint if it exists. Returns None if no checkpoint."""
        if not self.checkpoint_file.exists():
            return None
        with open(self.checkpoint_file, "r") as f:
            return yaml.safe_load(f)

    def save(self, checkpoint: dict) -> None:
        """Atomically write checkpoint state."""
        # Write to temp file first, then rename (atomic on POSIX)
        tmp_file = self.checkpoint_file.with_suffix(".tmp")
        with open(tmp_file, "w") as f:
            yaml.dump(checkpoint, f)
        tmp_file.rename(self.checkpoint_file)

    def clear(self) -> None:
        """Remove checkpoint file."""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()

    def get_byte_offset(self) -> int:
        """Return the byte offset to resume from, or 0 if no checkpoint."""
        ckpt = self.load()
        if ckpt is None:
            return 0
        return ckpt.get("last_byte_processed", 0)

    def get_current_bucket(self) -> Optional[str]:
        """Return the current daily bucket being written to."""
        ckpt = self.load()
        if ckpt is None:
            return None
        return ckpt.get("current_daily_bucket", None)

    def create_checkpoint(
        self,
        file: str,
        last_byte_processed: int,
        last_record_date: str,
        current_daily_bucket: str,
        records_processed: int,
        total_records_estimate: Optional[int] = None,
    ) -> None:
        """Save a checkpoint snapshot."""
        self.save({
            "file": file,
            "last_byte_processed": last_byte_processed,
            "last_record_date": last_record_date,
            "current_daily_bucket": current_daily_bucket,
            "records_processed": records_processed,
            "total_records_estimate": total_records_estimate,
        })


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Checkpoint manager for health ingestion")
    parser.add_argument("--state-dir", required=True, help="Directory for checkpoint state")
    parser.add_argument("--clear", action="store_true", help="Clear checkpoint and exit")
    parser.add_argument("--show", action="store_true", help="Show current checkpoint and exit")
    args = parser.parse_args()

    mgr = CheckpointManager(args.state_dir)

    if args.clear:
        mgr.clear()
        print("Checkpoint cleared.")
    elif args.show:
        ckpt = mgr.load()
        if ckpt:
            print(yaml.dump(ckpt))
        else:
            print("No checkpoint found.")
    else:
        parser.print_help()
