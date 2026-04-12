#!/usr/bin/env python3
"""Unit tests for refactored ingest.py."""

import os
import sys
import unittest
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# Allow running from any working directory: put this script's dir on sys.path
sys.path.insert(0, str(Path(__file__).parent))
import pymongo
from pymongo import UpdateOne

# Import after path setup
import ingest


class TestNormalizeType(unittest.TestCase):
    """Tests for normalize_type()."""

    def test_known_hk_types_map_correctly(self):
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierHeartRate"), "heart_rate")
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierHeartRateVariabilitySDNN"), "hrv_sdnn")
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierRestingHeartRate"), "resting_heart_rate")
        self.assertEqual(ingest.normalize_type("HKCategoryTypeIdentifierSleepAnalysis"), "sleep")
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierBloodGlucose"), "blood_glucose")
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierStepCount"), "step_count")
        self.assertEqual(ingest.normalize_type("HKQuantityTypeIdentifierVO2Max"), "vo2max")

    def test_unknown_type_falls_through(self):
        # Unknown type: lowercase + strip prefix
        result = ingest.normalize_type("HKQuantityTypeIdentifierUnknownMetric")
        self.assertEqual(result, "unknownmetric")

    def test_empty_type(self):
        result = ingest.normalize_type("")
        self.assertEqual(result, "")


class TestSanitizeUnit(unittest.TestCase):
    """Tests for unit sanitization."""

    def test_malformed_unit_with_float_leaked(self):
        # Apple Health bug: float leaks into unit field
        result = ingest._sanitize_unit("mmol<180.1558800000541>/L")
        self.assertEqual(result, "mmol/L")

    def test_clean_unit_unchanged(self):
        result = ingest._sanitize_unit("bpm")
        self.assertEqual(result, "bpm")

    def test_unit_with_spaces_unchanged(self):
        result = ingest._sanitize_unit("mg/dL")
        self.assertEqual(result, "mg/dL")

    def test_empty_unit(self):
        result = ingest._sanitize_unit("")
        self.assertEqual(result, "")


class TestParseDate(unittest.TestCase):
    """Tests for date parsing."""

    def test_iso8601_no_timezone(self):
        # No timezone suffix: parsed as naive, then made UTC-aware
        result = ingest._parse_date("2025-07-15T10:30:00")
        self.assertEqual(result, datetime(2025, 7, 15, 10, 30, 0, tzinfo=timezone.utc))

    def test_iso8601_with_z_timezone(self):
        result = ingest._parse_date("2025-07-15T10:30:00Z")
        self.assertEqual(result, datetime(2025, 7, 15, 10, 30, 0, tzinfo=timezone.utc))

    def test_iso8601_with_plus08_timezone(self):
        # +08:00 is converted to UTC (subtract 8 hours)
        result = ingest._parse_date("2025-07-15T10:30:00+08:00")
        self.assertEqual(result, datetime(2025, 7, 15, 2, 30, 0, tzinfo=timezone.utc))

    def test_empty_string_returns_none(self):
        result = ingest._parse_date("")
        self.assertIsNone(result)

    def test_invalid_string_returns_none(self):
        result = ingest._parse_date("not-a-date")
        self.assertIsNone(result)


class TestDeviceShort(unittest.TestCase):
    """Tests for device model extraction."""

    def test_full_device_string(self):
        result = ingest._device_short("Device/Watch7,5/<serial>")
        self.assertEqual(result, "Watch7")

    def test_device_string_no_variant(self):
        result = ingest._device_short("Device/AppleWatch")
        self.assertEqual(result, "AppleWatch")

    def test_empty_device(self):
        result = ingest._device_short("")
        self.assertIsNone(result)


class MockCollection:
    """In-memory mock of pymongo.collection.Collection for testing."""

    def __init__(self):
        self.docs: list[dict] = []
        self.bulk_ops: list = []

    def bulk_write(self, ops, ordered=False):
        self.bulk_ops.extend(ops)
        for op in ops:
            # pymongo UpdateOne uses __slots__; access via getattr on named slots
            filter_dict = getattr(op, "_filter", {})
            upsert = getattr(op, "_upsert", False)
            doc_dict = getattr(op, "_doc", {})
            doc = doc_dict.get("$setOnInsert") if isinstance(doc_dict, dict) else None

            if not upsert or doc is None:
                continue

            # Deduplicate on (timestamp, metric, value)
            key = (doc.get("timestamp"), doc.get("metadata", {}).get("metric"), doc.get("value"))
            existing = next(
                (d for d in self.docs
                 if (d.get("timestamp"), d.get("metadata", {}).get("metric"), d.get("value")) == key),
                None,
            )
            if not existing:
                self.docs.append(doc)

    def insert_many(self, docs, ordered=True):
        """Mock insert_many: inserts non-duplicates. Raises BulkWriteError with 11000 errors.

        When ordered=False, inserts all non-duplicate docs even if some fail with duplicate key errors.
        """
        from pymongo.errors import BulkWriteError
        write_errors = []
        new_docs = []
        for i, doc in enumerate(docs):
            key = (doc.get("timestamp"), doc.get("metadata", {}).get("metric"), doc.get("value"))
            existing = next(
                (d for d in self.docs
                 if (d.get("timestamp"), d.get("metadata", {}).get("metric"), d.get("value")) == key),
                None,
            )
            if existing:
                write_errors.append({"index": i, "code": 11000, "errmsg": "duplicate key"})
            else:
                new_docs.append(doc)
        if write_errors:
            if ordered:
                raise BulkWriteError({"writeErrors": write_errors})
            # ordered=False: insert all non-duplicates, remember errors
            self.docs.extend(new_docs)
            if write_errors:
                raise BulkWriteError({"writeErrors": write_errors})
        else:
            self.docs.extend(new_docs)

    def replace_one(self, filter_dict, replacement, upsert=False):
        # Simple mock: find by _id
        doc_id = filter_dict.get("_id")
        idx = next((i for i, d in enumerate(self.docs) if d.get("_id") == doc_id), None)
        if idx is not None:
            self.docs[idx] = replacement
        elif upsert:
            self.docs.append(replacement)

    def find_one(self, filter_dict):
        doc_id = filter_dict.get("_id")
        return next((d for d in self.docs if d.get("_id") == doc_id), None)

    def clear(self):
        self.docs.clear()
        self.bulk_ops.clear()


class MockDb:
    """In-memory mock of pymongo database for testing."""

    def __init__(self):
        self._collections: dict[str, MockCollection] = {}

    def __getitem__(self, name):
        if name not in self._collections:
            self._collections[name] = MockCollection()
        return self._collections[name]

    def __getattr__(self, name):
        return self[name]


class TestHealthRecordHandlerStartElement(unittest.TestCase):
    """Tests for HealthRecordHandler.startElement() building MongoDB documents."""

    def _handler_with_db(self, batch_size=1000):
        mock_db = MockDb()
        return ingest.HealthRecordHandler(mock_db, batch_size), mock_db

    def _make_attrs(self, **kwargs):
        """Create a mock SAX attribute object."""
        attrs = MagicMock()
        attrs.get = lambda k, d=None: kwargs.get(k, d)
        return attrs

    def test_builds_correct_document(self):
        handler, mock_db = self._handler_with_db()
        attrs = self._make_attrs(
            type="HKQuantityTypeIdentifierHeartRate",
            value="72",
            unit="count/min",
            startDate="2025-07-15T10:30:00+08:00",
            endDate="2025-07-15T10:30:01+08:00",
            sourceName="Apple\\Health",
            device="Device/Watch7,5/<serial>",
        )
        handler.startElement("Record", attrs)
        handler.endDocument()  # flush the batch

        self.assertEqual(handler.records_processed, 1)
        self.assertEqual(len(mock_db["metrics"].docs), 1)

        doc = mock_db["metrics"].docs[0]
        self.assertEqual(doc["metadata"]["metric"], "heart_rate")
        self.assertEqual(doc["metadata"]["source"], "Apple\\Health")
        self.assertEqual(doc["metadata"]["unit"], "count/min")
        self.assertEqual(doc["value"], 72.0)
        self.assertEqual(doc["device"], "Watch7")
        self.assertIsNotNone(doc["end_date"])

    def test_unknown_type_skipped(self):
        handler, mock_db = self._handler_with_db()
        attrs = self._make_attrs(type="HKQuantityTypeIdentifierUnknownType", value="100")
        handler.startElement("Record", attrs)
        self.assertEqual(handler.records_processed, 1)
        self.assertEqual(len(mock_db["metrics"].docs), 0)

    def test_empty_value_skipped(self):
        handler, mock_db = self._handler_with_db()
        attrs = self._make_attrs(type="HKQuantityTypeIdentifierHeartRate", value="")
        handler.startElement("Record", attrs)
        self.assertEqual(handler.records_processed, 1)
        self.assertEqual(len(mock_db["metrics"].docs), 0)

    def test_unit_sanitization_applied(self):
        handler, mock_db = self._handler_with_db()
        attrs = self._make_attrs(
            type="HKQuantityTypeIdentifierBloodGlucose",
            value="5.4",
            unit="mmol<180.155>/L",
            startDate="2025-07-15T10:30:00+08:00",
        )
        handler.startElement("Record", attrs)
        handler.endDocument()  # flush the batch
        doc = mock_db["metrics"].docs[0]
        self.assertEqual(doc["metadata"]["unit"], "mmol/L")

    def test_date_filter_excludes_early_records(self):
        handler, mock_db = self._handler_with_db()
        handler.start_date_filter = datetime(2025, 7, 15, tzinfo=timezone.utc)
        attrs = self._make_attrs(
            type="HKQuantityTypeIdentifierHeartRate",
            value="72",
            startDate="2025-07-10T10:30:00+08:00",
        )
        handler.startElement("Record", attrs)
        self.assertEqual(handler.records_processed, 1)
        self.assertEqual(len(mock_db["metrics"].docs), 0)

    def test_date_filter_excludes_late_records(self):
        handler, mock_db = self._handler_with_db()
        handler.end_date_filter = datetime(2025, 7, 15, tzinfo=timezone.utc)
        attrs = self._make_attrs(
            type="HKQuantityTypeIdentifierHeartRate",
            value="72",
            startDate="2025-07-20T10:30:00+08:00",
        )
        handler.startElement("Record", attrs)
        self.assertEqual(handler.records_processed, 1)
        self.assertEqual(len(mock_db["metrics"].docs), 0)

    def test_non_record_element_ignored(self):
        handler, mock_db = self._handler_with_db()
        attrs = self._make_attrs()
        handler.startElement("SomethingElse", attrs)
        self.assertEqual(handler.records_processed, 0)


class TestHealthRecordHandlerFlushBatch(unittest.TestCase):
    """Tests for HealthRecordHandler._flush_batch()."""

    def _handler_with_db(self, batch_size=1000):
        mock_db = MockDb()
        return ingest.HealthRecordHandler(mock_db, batch_size), mock_db

    def _make_attrs(self, **kwargs):
        attrs = MagicMock()
        attrs.get = lambda k, d=None: kwargs.get(k, d)
        return attrs

    def test_flushes_batch_to_metrics_collection(self):
        handler, mock_db = self._handler_with_db(batch_size=1000)
        # Add 3 records manually
        for i, val in enumerate([70, 72, 68]):
            attrs = self._make_attrs(
                type="HKQuantityTypeIdentifierHeartRate",
                value=str(val),
                startDate=f"2025-07-15T10:3{i}:00+08:00",
            )
            handler.startElement("Record", attrs)

        self.assertEqual(len(mock_db["metrics"].docs), 0)  # not flushed yet
        handler._flush_batch()
        self.assertEqual(len(mock_db["metrics"].docs), 3)

    def test_partial_batch_flushed_on_endDocument(self):
        handler, mock_db = self._handler_with_db(batch_size=1000)
        for i, val in enumerate([70, 72, 68]):
            attrs = self._make_attrs(
                type="HKQuantityTypeIdentifierHeartRate",
                value=str(val),
                startDate=f"2025-07-15T10:3{i}:00+08:00",
            )
            handler.startElement("Record", attrs)

        self.assertEqual(len(mock_db["metrics"].docs), 0)  # only 3 records, batch_size=1000
        handler.endDocument()
        self.assertEqual(len(mock_db["metrics"].docs), 3)

    def test_batch_size_triggers_auto_flush(self):
        handler, mock_db = self._handler_with_db(batch_size=2)
        for i, val in enumerate([70, 72]):
            attrs = self._make_attrs(
                type="HKQuantityTypeIdentifierHeartRate",
                value=str(val),
                startDate=f"2025-07-15T10:3{i}:00+08:00",
            )
            handler.startElement("Record", attrs)

        # After 2 records (== batch_size), auto-flush
        self.assertEqual(len(mock_db["metrics"].docs), 2)
        # Third record triggers another flush
        attrs = self._make_attrs(
            type="HKQuantityTypeIdentifierHeartRate",
            value="68",
            startDate="2025-07-15T10:30:00+08:00",
        )
        handler.startElement("Record", attrs)
        handler.endDocument()
        self.assertEqual(len(mock_db["metrics"].docs), 3)


class TestIdempotency(unittest.TestCase):
    """Tests for idempotent ingestion (upsert dedup)."""

    def _handler_with_db(self):
        mock_db = MockDb()
        return ingest.HealthRecordHandler(mock_db, batch_size=1000), mock_db

    def _make_attrs(self, **kwargs):
        attrs = MagicMock()
        attrs.get = lambda k, d=None: kwargs.get(k, d)
        return attrs

    def test_same_record_twice_produces_single_document(self):
        handler, mock_db = self._handler_with_db()
        common_attrs = dict(
            type="HKQuantityTypeIdentifierHeartRate",
            value="72",
            unit="count/min",
            startDate="2025-07-15T10:30:00+08:00",
            sourceName="Apple\\Health",
            device="Device/Watch7,5/<serial>",
        )

        handler.startElement("Record", self._make_attrs(**common_attrs))
        handler.startElement("Record", self._make_attrs(**common_attrs))
        handler.endDocument()

        # Both upserts target the same (timestamp, metric, value) key
        # The second upsert should not create a duplicate
        self.assertEqual(len(mock_db["metrics"].docs), 1)


class TestCheckpointRoundTrip(unittest.TestCase):
    """Tests for MongoDB checkpoint save/load round-trip."""

    def _engine(self):
        mock_db = MockDb()
        engine = ingest.IngestEngine("mock://", "test_db", batch_size=100)
        engine.db = mock_db
        engine.client = MagicMock()
        return engine, mock_db

    def _make_attrs(self, **kwargs):
        attrs = MagicMock()
        attrs.get = lambda k, d=None: kwargs.get(k, d)
        return attrs

    def test_update_checkpoint_writes_singleton(self):
        engine, mock_db = self._engine()
        handler = ingest.HealthRecordHandler(mock_db, batch_size=1000)
        handler.records_processed = 42
        handler.last_record_date = "2025-07-15"

        handler._update_checkpoint("/path/to/export.xml", 123456)

        doc = mock_db["checkpoint"].find_one({"_id": "ingest_checkpoint"})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["file"], "/path/to/export.xml")
        self.assertEqual(doc["byte_offset"], 123456)
        self.assertEqual(doc["records_processed"], 42)
        self.assertEqual(doc["status"], "in_progress")

    def test_mark_complete_updates_status(self):
        engine, mock_db = self._engine()
        handler = ingest.HealthRecordHandler(mock_db, batch_size=1000)
        handler.records_processed = 100
        handler.last_record_date = "2025-07-15"

        handler._mark_complete("/path/to/export.xml", 999999)

        doc = mock_db["checkpoint"].find_one({"_id": "ingest_checkpoint"})
        self.assertEqual(doc["status"], "completed")
        self.assertEqual(doc["byte_offset"], 999999)

    def test_resume_loads_checkpoint_byte_offset(self):
        engine, mock_db = self._engine()
        # Pre-populate checkpoint
        mock_db["checkpoint"].replace_one(
            {"_id": "ingest_checkpoint"},
            {
                "_id": "ingest_checkpoint",
                "file": "/path/to/export.xml",
                "byte_offset": 500000,
                "records_processed": 10000,
                "status": "in_progress",
            },
            upsert=True,
        )

        ckpt = engine._load_checkpoint()
        self.assertIsNotNone(ckpt)
        self.assertEqual(ckpt["byte_offset"], 500000)
        self.assertEqual(ckpt["file"], "/path/to/export.xml")

    def test_resume_returns_none_when_no_checkpoint(self):
        engine, mock_db = self._engine()
        ckpt = engine._load_checkpoint()
        self.assertIsNone(ckpt)


if __name__ == "__main__":
    unittest.main()
