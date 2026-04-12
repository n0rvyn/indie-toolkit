#!/usr/bin/env python3
"""
Streaming XML ingestion script for Apple Health export data.
Supports resumable processing via MongoDB checkpoint.

Usage:
    python ingest.py --source <file> [--database health] [--batch-size 1000]
    python ingest.py --source <dir> [--database health]
    python ingest.py --resume [--database health]
    python ingest.py --source <file> --start-date 2025-04-01 --end-date 2026-03-30
"""

import argparse
import os
import re
import sys
import xml.sax
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Optional

import pymongo

# Record type normalization: Apple Health type → metric key
TYPE_MAP = {
    "HKQuantityTypeIdentifierHeartRate": "heart_rate",
    "HKQuantityTypeIdentifierHeartRateVariabilitySDNN": "hrv_sdnn",
    "HKQuantityTypeIdentifierRestingHeartRate": "resting_heart_rate",
    "HKQuantityTypeIdentifierWalkingHeartRateAverage": "walking_heart_rate_avg",
    "HKQuantityTypeIdentifierVO2Max": "vo2max",
    "HKQuantityTypeIdentifierStepCount": "step_count",
    "HKQuantityTypeIdentifierDistanceWalkingRunning": "distance",
    "HKQuantityTypeIdentifierDistanceCycling": "distance_cycling",
    "HKQuantityTypeIdentifierActiveEnergyBurned": "active_energy",
    "HKQuantityTypeIdentifierBasalEnergyBurned": "basal_energy",
    "HKQuantityTypeIdentifierFlightsClimbed": "flights_climbed",
    "HKQuantityTypeIdentifierAppleExerciseTime": "exercise_time",
    "HKQuantityTypeIdentifierAppleStandTime": "stand_time",
    "HKCategoryTypeIdentifierSleepAnalysis": "sleep",
    "HKQuantityTypeIdentifierBloodGlucose": "blood_glucose",
    "HKQuantityTypeIdentifierBloodPressureSystolic": "bp_sys",
    "HKQuantityTypeIdentifierBloodPressureDiastolic": "bp_dia",
    "HKQuantityTypeIdentifierOxygenSaturation": "spo2",
    "HKQuantityTypeIdentifierRespiratoryRate": "resp_rate",
    "HKQuantityTypeIdentifierBodyTemperature": "body_temp",
    "HKQuantityTypeIdentifierBodyMass": "body_mass",
    "HKQuantityTypeIdentifierBodyMassIndex": "bmi",
    "HKQuantityTypeIdentifierBodyFatPercentage": "body_fat_pct",
    "HKQuantityTypeIdentifierLeanBodyMass": "lean_mass",
    "HKQuantityTypeIdentifierDietaryWater": "water",
    "HKQuantityTypeIdentifierDietaryEnergyConsumed": "calories_consumed",
    "HKQuantityTypeIdentifierDietaryProtein": "protein",
    "HKQuantityTypeIdentifierDietaryCarbohydrates": "carbs",
    "HKQuantityTypeIdentifierDietaryFatTotal": "fat_total",
    "HKQuantityTypeIdentifierDietaryFiber": "fiber",
    "HKQuantityTypeIdentifierDietarySugar": "sugar",
    "HKQuantityTypeIdentifierDietarySodium": "sodium",
    "HKQuantityTypeIdentifierDietaryCholesterol": "cholesterol",
    "HKQuantityTypeIdentifierCyclingSpeed": "cycling_speed",
    "HKQuantityTypeIdentifierCyclingCadence": "cycling_cadence",
    "HKQuantityTypeIdentifierCyclingPower": "cycling_power",
    "HKQuantityTypeIdentifierRunningSpeed": "running_speed",
    "HKQuantityTypeIdentifierRunningStrideLength": "running_stride_length",
    "HKQuantityTypeIdentifierRunningVerticalOscillation": "running_vertical_osc",
    "HKQuantityTypeIdentifierRunningGroundContactTime": "running_gct",
    "HKQuantityTypeIdentifierRunningPower": "running_power",
    "HKQuantityTypeIdentifierHeartRateRecoveryOneMinute": "hr_recovery_1min",
    "HKQuantityTypeIdentifierWalkingSpeed": "walking_speed",
    "HKQuantityTypeIdentifierWalkingStepLength": "walking_step_length",
    "HKQuantityTypeIdentifierWalkingAsymmetryPercentage": "walking_asymmetry",
    "HKQuantityTypeIdentifierWalkingDoubleSupportPercentage": "walking_dbl_support",
    "HKQuantityTypeIdentifierStairAscentSpeed": "stair_up_speed",
    "HKQuantityTypeIdentifierStairDescentSpeed": "stair_down_speed",
    "HKQuantityTypeIdentifierSixMinuteWalkTestDistance": "6min_walk_distance",
    "HKQuantityTypeIdentifierAppleWalkingSteadiness": "walking_steadiness",
    "HKQuantityTypeIdentifierEnvironmentalAudioExposure": "env_audio_exposure",
    "HKQuantityTypeIdentifierHeadphoneAudioExposure": "headphone_exposure",
    "HKQuantityTypeIdentifierEnvironmentalSoundReduction": "env_sound_reduction",
    "HKQuantityTypeIdentifierTimeInDaylight": "daylight_time",
    "HKQuantityTypeIdentifierPhysicalEffort": "physical_effort",
    "HKQuantityTypeIdentifierAppleSleepingWristTemperature": "sleep_wrist_temp",
    "HKDataTypeSleepDurationGoal": "sleep_goal",
}


def normalize_type(hk_type: str) -> str:
    """Normalize Apple Health type string to metric key."""
    return TYPE_MAP.get(hk_type, hk_type.lower().replace("hkquantitytypeidentifier", "").replace("hkcategorytypeidentifier", "").replace("hkdtype", ""))


def _sanitize_unit(unit: str) -> str:
    """Remove garbage from malformed unit strings (e.g. 'mmol<180.155>/L')."""
    if unit and "<" in unit:
        unit = re.sub(r"<[^>]+>", "", unit)
    return unit


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse an Apple Health ISO 8601 date string to a UTC-aware datetime.

    Handles Z suffix and +HH:MM offsets by converting to UTC-aware datetime.
    """
    if not date_str:
        return None
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, AttributeError):
        return None


def _device_short(device: str) -> Optional[str]:
    """Extract model identifier from full device string."""
    if not device:
        return None
    # Device strings look like "Device/<model>,<variant>/<details>"
    parts = device.split("/")
    if len(parts) >= 2:
        return parts[1].split(",")[0] if "," in parts[1] else parts[1]
    return device[:64]


class HealthRecordHandler(xml.sax.ContentHandler):
    """SAX handler that writes records directly to MongoDB in batches."""

    def __init__(self, db, batch_size: int = 1000):
        self.db = db
        self.batch_size = batch_size
        self.batch: list[dict] = []
        # In-batch deduplication set: (timestamp, metric, value) keys already in batch
        self._seen_keys: set[tuple] = set()
        self.records_processed = 0
        self.last_record_date: Optional[str] = None
        self.bytes_processed = 0
        # Date filter bounds (set by IngestEngine)
        self.start_date_filter: Optional[datetime] = None
        self.end_date_filter: Optional[datetime] = None

    def _flush_batch(self):
        """Insert accumulated batch to MongoDB. Uses insert_many (time-series collections do not support UpdateOne upsert)."""
        if not self.batch:
            return
        try:
            self.db.metrics.insert_many(self.batch, ordered=False)
        except pymongo.errors.BulkWriteError as e:
            # Ignore duplicate key errors (code 11000) for idempotent re-runs
            for err in e.details.get("writeErrors", []):
                if err.get("code") != 11000:
                    raise
        self.batch.clear()
        self._seen_keys.clear()  # Free memory; cross-batch dupes near-impossible in chronological exports

    def _update_checkpoint(self, file: str, byte_offset: int):
        """Persist checkpoint state to MongoDB singleton."""
        self.db.checkpoint.replace_one(
            {"_id": "ingest_checkpoint"},
            {
                "_id": "ingest_checkpoint",
                "file": file,
                "byte_offset": byte_offset,
                "last_record_date": self.last_record_date,
                "records_processed": self.records_processed,
                "status": "in_progress",
                "updated_at": datetime.now(timezone.utc),
            },
            upsert=True,
        )

    def _mark_complete(self, file: str, file_size: int):
        """Mark ingest as completed in checkpoint."""
        self.db.checkpoint.replace_one(
            {"_id": "ingest_checkpoint"},
            {
                "_id": "ingest_checkpoint",
                "file": file,
                "byte_offset": file_size,
                "last_record_date": self.last_record_date,
                "records_processed": self.records_processed,
                "status": "completed",
                "updated_at": datetime.now(timezone.utc),
            },
            upsert=True,
        )

    # xml.sax ContentHandler interface

    def startElement(self, name: str, attrs):
        if name != "Record":
            return

        hk_type = attrs.get("type", "")
        rec_type = normalize_type(hk_type)
        # Skip unknown types
        if rec_type not in TYPE_MAP.values() and rec_type not in TYPE_MAP:
            self.records_processed += 1
            return

        value_str = attrs.get("value", "")
        if not value_str:
            self.records_processed += 1
            return

        try:
            value = float(value_str)
        except (ValueError, TypeError):
            self.records_processed += 1
            return

        unit = _sanitize_unit(attrs.get("unit", ""))
        start_date = attrs.get("startDate", "")
        end_date = attrs.get("endDate", "")
        source = attrs.get("sourceName", "")
        device = _device_short(attrs.get("device", ""))

        start_dt = _parse_date(start_date)
        if start_dt is None:
            self.records_processed += 1
            return

        # Apply date filters
        if self.start_date_filter and start_dt < self.start_date_filter:
            self.records_processed += 1
            return
        if self.end_date_filter and start_dt > self.end_date_filter:
            self.records_processed += 1
            return

        end_dt = _parse_date(end_date) if end_date else None

        doc = {
            "timestamp": start_dt,
            "metadata": {
                "metric": rec_type,
                "source": source or "unknown",
                "unit": unit,
            },
            "value": value,
            "device": device,
            "end_date": end_dt,
        }

        # In-batch deduplication: skip if same (timestamp, metric, value) already in batch
        key = (start_dt, rec_type, value)
        if key in self._seen_keys:
            self.records_processed += 1
            return
        self._seen_keys.add(key)

        self.batch.append(doc)
        self.last_record_date = start_date[:10] if start_date else None

        if len(self.batch) >= self.batch_size:
            self._flush_batch()

        if self.records_processed > 0 and self.records_processed % 10000 == 0:
            print(f"  {self.records_processed:,} records processed...", flush=True)

        self.records_processed += 1

    def endDocument(self):
        self._flush_batch()

    def characters(self, content):
        self.bytes_processed += len(content)


class IngestEngine:
    """Streaming XML ingestion engine with MongoDB checkpoint support."""

    def __init__(self, mongo_uri: str, database: str, batch_size: int = 1000):
        self.mongo_uri = mongo_uri
        self.database_name = database
        self.batch_size = batch_size
        self.client: Optional[pymongo.MongoClient] = None
        self.db = None

    def _connect(self):
        if self.client is None:
            self.client = pymongo.MongoClient(self.mongo_uri)
            self.db = self.client[self.database_name]
            # Ensure ingest_log collection has unique index on (file, chunk_start)
            self.db.ingest_log.create_index(
                [("file", 1), ("chunk_start", 1)],
                unique=True,
                background=True,
            )

    def close(self):
        if self.client:
            self.client.close()
            self.client = None
            self.db = None

    def _load_checkpoint(self) -> Optional[dict]:
        """Load ingest checkpoint from MongoDB, or None if no checkpoint exists."""
        self._connect()
        return self.db.checkpoint.find_one({"_id": "ingest_checkpoint"})

    def _get_handler(self) -> HealthRecordHandler:
        """Create a configured SAX handler with MongoDB connection."""
        self._connect()
        handler = HealthRecordHandler(self.db, self.batch_size)
        return handler

    def ingest_file(
        self,
        filepath: str,
        resume_from_byte: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """Ingest a single XML file, optionally resuming from a byte offset."""
        filepath = Path(filepath).expanduser()
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        file_size = filepath.stat().st_size

        handler = self._get_handler()

        # Configure date filters on handler (UTC-aware)
        if start_date:
            handler.start_date_filter = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        if end_date:
            handler.end_date_filter = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)

        # Save initial checkpoint
        handler._update_checkpoint(str(filepath), resume_from_byte)

        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)

        print(f"Ingesting {filepath} ({file_size:,} bytes)...")
        if resume_from_byte > 0:
            print(f"Resuming from byte {resume_from_byte:,}")

        with open(filepath, "r", errors="ignore") as f:
            if resume_from_byte > 0:
                f.seek(resume_from_byte)

            chunk_size_bytes = 10 * 1024 * 1024  # 10 MB chunks
            chunk_num = 0

            while True:
                chunk = f.read(chunk_size_bytes)
                if not chunk:
                    break

                chunk_start = f.tell() - len(chunk)
                chunk_end = f.tell()
                chunk_num += 1
                pct = chunk_end / file_size * 100

                # Cross-run idempotency: skip chunks already ingested
                already = self.db.ingest_log.find_one({"file": str(filepath), "chunk_start": chunk_start})
                if already:
                    print(f"Chunk {chunk_num}: bytes {chunk_start:,} – {chunk_end:,} ({pct:.1f}%) — skipped (already ingested)", flush=True)
                    continue

                print(f"Chunk {chunk_num}: bytes {chunk_start:,} – {chunk_end:,} ({pct:.1f}%)", flush=True)

                sax_input = xml.sax.InputSource(StringIO(chunk))
                sax_input.setSystemId(str(filepath))
                try:
                    parser.parse(sax_input)
                except xml.sax.SAXException as e:
                    print(f"  SAX warning (continuing): {e}", file=sys.stderr)

                # Log this chunk as ingested (cross-run dedup)
                try:
                    self.db.ingest_log.insert_one({
                        "file": str(filepath),
                        "chunk_start": chunk_start,
                        "chunk_end": chunk_end,
                        "records_at": handler.records_processed,
                        "ingested_at": datetime.now(timezone.utc),
                    })
                except pymongo.errors.DuplicateKeyError:
                    pass  # Already logged by a concurrent run

                # Update checkpoint mid-chunk
                handler._update_checkpoint(str(filepath), chunk_end)

                if f.tell() >= file_size:
                    break

        # Final flush (endDocument already calls _flush_batch, but guard here too)
        handler._flush_batch()

        # Mark complete
        handler._mark_complete(str(filepath), file_size)

        print(f"Done: {handler.records_processed:,} records")
        return {
            "records_processed": handler.records_processed,
            "last_record_date": handler.last_record_date,
        }

    def ingest_directory(self, dirpath: str) -> dict:
        """Ingest all XML files in a directory."""
        dirpath = Path(dirpath).expanduser()
        xml_files = sorted(dirpath.glob("*.xml"))
        total_records = 0

        for xml_file in xml_files:
            result = self.ingest_file(str(xml_file), resume_from_byte=0)
            total_records += result["records_processed"]

        return {
            "records_processed": total_records,
            "files_processed": len(xml_files),
        }

    def resume(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> dict:
        """Resume from the last MongoDB checkpoint."""
        ckpt = self._load_checkpoint()
        if not ckpt:
            raise RuntimeError("No checkpoint found. Use --source to specify a file.")
        return self.ingest_file(
            ckpt["file"],
            resume_from_byte=ckpt.get("byte_offset", 0),
            start_date=start_date,
            end_date=end_date,
        )


def main():
    default_uri = os.environ.get("MDB_MCP_CONNECTION_STRING", "")

    parser = argparse.ArgumentParser(description="Apple Health XML ingestion to MongoDB")
    parser.add_argument("--source", help="XML file or directory of XML files to ingest")
    parser.add_argument("--mongo-uri", default=default_uri, help=f"MongoDB connection string (default: $MDB_MCP_CONNECTION_STRING)")
    parser.add_argument("--database", default="health", help="MongoDB database name (default: health)")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for MongoDB writes (default: 1000)")
    parser.add_argument("--resume", action="store_true", help="Resume from last MongoDB checkpoint")
    parser.add_argument("--start-date", help="Filter records starting from this date (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="Filter records up to this date (YYYY-MM-DD)")
    args = parser.parse_args()

    if not args.mongo_uri:
        print("Error: --mongo-uri required or MDB_MCP_CONNECTION_STRING env var must be set", file=sys.stderr)
        sys.exit(1)

    engine = IngestEngine(args.mongo_uri, args.database, args.batch_size)

    try:
        if args.resume:
            result = engine.resume(start_date=args.start_date, end_date=args.end_date)
            print(f"Resume complete: {result['records_processed']:,} records")
        elif args.source:
            source_path = Path(args.source).expanduser()
            if source_path.is_dir():
                result = engine.ingest_directory(str(source_path))
                print(f"Ingestion complete: {result['records_processed']:,} records, {result['files_processed']} files")
            else:
                result = engine.ingest_file(str(source_path), start_date=args.start_date, end_date=args.end_date)
                print(f"Ingestion complete: {result['records_processed']:,} records")
        else:
            parser.print_help()
            sys.exit(1)
    finally:
        engine.close()


if __name__ == "__main__":
    main()
