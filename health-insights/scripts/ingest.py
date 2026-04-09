#!/usr/bin/env python3
"""
Streaming XML ingestion script for Apple Health export data.
Supports resumable processing via checkpoint files.

Usage:
    python ingest.py --source <file> --checkpoint-dir <dir> --vault-dir <dir> [--finalize]
    python ingest.py --source <dir> --checkpoint-dir <dir> --vault-dir <dir> [--finalize]
    python ingest.py --resume --checkpoint-dir <dir> --vault-dir <dir> [--finalize]
"""

import argparse
import os
import sys
import xml.sax
import yaml
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TextIO, Optional

# Record type normalization: Apple Health type → vault file name
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
    "HKQuantityTypeIdentifierBloodGlucose": "blood_glucose",
}


def normalize_type(hk_type: str) -> str:
    """Normalize Apple Health type string to vault key name."""
    return TYPE_MAP.get(hk_type, hk_type.lower().replace("hkquantitytypeidentifier", "").replace("hkcategorytypeidentifier", "").replace("hkdtype", ""))


class HealthRecordHandler(xml.sax.ContentHandler):
    """SaxParser handler that accumulates records into daily buckets."""

    def __init__(self, buffer_dir: Path, chunk_size_bytes: int = 10 * 1024 * 1024):
        self.buffer_dir = Path(buffer_dir)
        self.chunk_size_bytes = chunk_size_bytes
        self.bytes_processed = 0
        self.records_processed = 0
        self.last_byte_processed = 0
        self.last_record_date = None
        self.current_bucket = None  # YYYY-MM-DD

        # Per-type accumulators: { date -> { type -> list[records] } }
        self.buckets = defaultdict(lambda: defaultdict(list))
        # Open file handles for append mode
        self._handles = {}

    def _get_handle(self, date: str, rec_type: str) -> TextIO:
        """Get or create an append handle for a date/type combination."""
        key = (date, rec_type)
        if key not in self._handles:
            date_dir = self.buffer_dir / date
            date_dir.mkdir(parents=True, exist_ok=True)
            f = open(date_dir / f"{rec_type}.tmp", "a")
            self._handles[key] = f
        return self._handles[key]

    def _close_all_handles(self):
        """Close all open file handles."""
        for f in self._handles.values():
            f.close()
        self._handles = {}

    def _flush_bucket(self, date: str):
        """Flush all handles for a specific date."""
        for (d, _), f in list(self._handles.items()):
            if d == date:
                f.flush()
                os.fsync(f.fileno())

    def _get_date_from_pos(self, pos: int, f: TextIO) -> int:
        """Seek to position and return the byte offset of the next <Record."""
        # This is called during resume; we seek to the byte and scan for next Record start
        return pos

    # xml.sax ContentHandler interface

    def startElement(self, name: str, attrs):
        if name != "Record":
            return

        hk_type = attrs.get("type", "")
        rec_type = normalize_type(hk_type)
        if rec_type not in TYPE_MAP.values() and rec_type not in TYPE_MAP:
            # Unknown type — skip writing but count it
            self.records_processed += 1
            return

        value = attrs.get("value", "")
        unit = attrs.get("unit", "")
        # Sanitize unit: Apple Health export sometimes has malformed values like
        # "mmol<180.1558800000541>/L" where a float leaked into the unit field.
        # Keep only the first space-delimited token group that looks like a unit.
        if unit and "<" in unit:
            # Apple Health sometimes puts a float in the unit field (e.g. "mmol<180.155>/L")
            # Remove the garbage embedded in angle brackets
            import re
            unit = re.sub(r'<[^>]+>', '', unit)
        start_date = attrs.get("startDate", "")
        end_date = attrs.get("endDate", "")
        source = attrs.get("sourceName", "")
        device = attrs.get("device", "")
        creation_date = attrs.get("creationDate", "")

        # Parse date to get YYYY-MM-DD bucket
        try:
            dt = datetime.fromisoformat(start_date.replace("Z", "+00:00").replace("+08:00", ""))
            date_str = dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            date_str = "unknown"

        if self.current_bucket is None:
            self.current_bucket = date_str
        elif date_str != self.current_bucket:
            # Date changed — flush previous bucket
            self._flush_bucket(self.current_bucket)
            self.current_bucket = date_str

        # Write to append-only tmp file
        record = {
            "type": rec_type,
            "value": value,
            "unit": unit,
            "start_date": start_date,
            "end_date": end_date,
            "source": source,
            "device": device,
            "creation_date": creation_date,
        }

        try:
            f = self._get_handle(date_str, rec_type)
            f.write(yaml.safe_dump(record, allow_unicode=True))
            f.write("---\n")
        except Exception as e:
            print(f"Error writing record: {e}", file=sys.stderr)

        self.last_record_date = date_str
        self.records_processed += 1

        if self.records_processed % 10000 == 0:
            print(f"  {self.records_processed:,} records processed...", flush=True)

    def endDocument(self):
        self._close_all_handles()

    def characters(self, content):
        self.bytes_processed += len(content)


class IngestEngine:
    """Streaming XML ingestion engine with checkpoint support."""

    def __init__(self, vault_dir: str, checkpoint_dir: str, chunk_size_mb: int = 10):
        self.vault_dir = Path(vault_dir).expanduser()
        self.checkpoint_dir = Path(checkpoint_dir).expanduser()
        self.chunk_size_bytes = chunk_size_mb * 1024 * 1024
        self.buffer_dir = self.vault_dir / ".ingest_buffer"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.buffer_dir.mkdir(parents=True, exist_ok=True)

        # Import checkpoint manager
        from checkpoint import CheckpointManager
        self.ckpt = CheckpointManager(str(self.checkpoint_dir))

    def ingest_file(
        self,
        filepath: str,
        resume_from_byte: int = 0,
        total_estimate: Optional[int] = None,
        finalize: bool = True,
    ) -> dict:
        """Ingest a single XML file, optionally resuming from a byte offset."""
        filepath = Path(filepath).expanduser()
        file_size = filepath.stat().st_size

        handler = HealthRecordHandler(str(self.buffer_dir), self.chunk_size_bytes)

        # Save initial checkpoint
        self.ckpt.create_checkpoint(
            file=str(filepath),
            last_byte_processed=resume_from_byte,
            last_record_date="unknown",
            current_daily_bucket="unknown",
            records_processed=0,
            total_records_estimate=total_estimate,
        )

        parser = xml.sax.make_parser()
        parser.setContentHandler(handler)

        print(f"Ingesting {filepath} ({file_size:,} bytes)...")
        if resume_from_byte > 0:
            print(f"Resuming from byte {resume_from_byte:,}")

        with open(filepath, "r", errors="ignore") as f:
            if resume_from_byte > 0:
                f.seek(resume_from_byte)

            chunk_num = 0
            while True:
                # Read chunk
                chunk = f.read(self.chunk_size_bytes)
                if not chunk:
                    break

                chunk_start = f.tell() - len(chunk)
                chunk_num += 1
                print(f"Chunk {chunk_num}: bytes {chunk_start:,} – {f.tell():,} ({f.tell()/file_size*100:.1f}%)", flush=True)

                # Parse this chunk
                from io import StringIO
                sax_input = xml.sax.InputSource(StringIO(chunk))
                sax_input.setSystemId(filepath)
                try:
                    parser.parse(sax_input)
                except xml.sax.SAXException as e:
                    print(f"  SAX warning (continuing): {e}", file=sys.stderr)

                # Update checkpoint mid-chunk
                self.ckpt.create_checkpoint(
                    file=str(filepath),
                    last_byte_processed=f.tell(),
                    last_record_date=handler.last_record_date or "unknown",
                    current_daily_bucket=handler.current_bucket or "unknown",
                    records_processed=handler.records_processed,
                    total_records_estimate=total_estimate,
                )

                if f.tell() >= file_size:
                    break

        print(f"Done: {handler.records_processed:,} records across {len(handler.buckets)} days")

        if finalize:
            self.finalize()

        # Mark complete
        self.ckpt.create_checkpoint(
            file=str(filepath),
            last_byte_processed=file_size,
            last_record_date=handler.last_record_date,
            current_daily_bucket=handler.current_bucket,
            records_processed=handler.records_processed,
            total_records_estimate=total_estimate,
        )

        return {
            "records_processed": handler.records_processed,
            "days": sorted(handler.buckets.keys()),
        }

    def ingest_directory(self, dirpath: str, finalize: bool = True) -> dict:
        """Ingest all XML files in a directory."""
        dirpath = Path(dirpath).expanduser()
        xml_files = sorted(dirpath.glob("*.xml"))
        total_records = 0
        all_days = set()

        for xml_file in xml_files:
            result = self.ingest_file(str(xml_file), resume_from_byte=0, finalize=False)
            total_records += result["records_processed"]
            all_days.update(result["days"])

        if finalize:
            self.finalize()

        return {
            "records_processed": total_records,
            "days": sorted(all_days),
        }

    def finalize(self) -> None:
        """Convert buffer/*.tmp files into daily/*.yaml vault files."""
        if not self.buffer_dir.exists():
            return

        daily_dir = self.vault_dir / "daily"
        daily_dir.mkdir(exist_ok=True)

        for date_dir in sorted(self.buffer_dir.iterdir()):
            if not date_dir.is_dir():
                continue
            date_str = date_dir.name
            target_date_dir = daily_dir / date_str
            target_date_dir.mkdir(exist_ok=True)

            for tmp_file in sorted(date_dir.glob("*.tmp")):
                rec_type = tmp_file.stem  # e.g. "heart_rate"
                output_file = target_date_dir / f"{rec_type}.yaml"

                # Read all records from tmp
                records = []
                with open(tmp_file, "r") as f:
                    content = f.read()

                # Split on yaml document separator
                parts = content.split("---\n")
                for part in parts:
                    part = part.strip()
                    if not part:
                        continue
                    try:
                        records.append(yaml.safe_load(part))
                    except yaml.YAMLError:
                        continue

                # Write structured daily file
                data = {
                    "type": "daily",
                    "source": "apple-health-export",
                    "date": date_str,
                    "records": records,
                }

                with open(output_file, "w") as f:
                    f.write("---\n")
                    f.write(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))

                print(f"  Written: {output_file.relative_to(self.vault_dir)} ({len(records)} records)")

        # Clean up buffer
        import shutil
        shutil.rmtree(self.buffer_dir)
        print("Buffer finalized and cleared.")


def main():
    parser = argparse.ArgumentParser(description="Apple Health XML ingestion")
    parser.add_argument("--source", help="XML file or directory of XML files to ingest")
    parser.add_argument("--checkpoint-dir", default="~/.adam/state/health-insights/checkpoints", help="Checkpoint directory")
    parser.add_argument("--vault-dir", default="~/Obsidian/HealthVault", help="HealthVault directory")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--finalize", action="store_true", help="Finalize buffer to vault YAML files")
    parser.add_argument("--chunk-size-mb", type=int, default=10, help="Chunk size in MB for streaming")
    args = parser.parse_args()

    engine = IngestEngine(args.vault_dir, args.checkpoint_dir, args.chunk_size_mb)

    if args.resume:
        ckpt = engine.ckpt.load()
        if ckpt:
            result = engine.ingest_file(
                ckpt["file"],
                resume_from_byte=ckpt["last_byte_processed"],
                total_estimate=ckpt.get("total_records_estimate"),
                finalize=args.finalize,
            )
        else:
            print("No checkpoint found. Use --source to specify a file.")
            sys.exit(1)
    elif args.source:
        source_path = Path(args.source).expanduser()
        if source_path.is_dir():
            result = engine.ingest_directory(str(source_path), finalize=args.finalize)
        else:
            result = engine.ingest_file(str(source_path), finalize=args.finalize)
        print(f"Ingestion complete: {result['records_processed']:,} records, {len(result['days'])} days")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
