#!/usr/bin/env python3
"""
Migrate audit logs from JSONL files to SQLite database
"""
import json
import logging
from pathlib import Path
from datetime import datetime
from database import database

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate_audit_logs():
    """Migrate audit logs from files to SQLite"""
    audit_dir = Path("audit_logs")

    if not audit_dir.exists():
        logger.info("No audit_logs directory found, skipping migration")
        return 0

    total_migrated = 0

    # Find all audit log files
    for log_file in audit_dir.glob("audit_*.jsonl"):
        logger.info(f"Processing {log_file.name}...")

        try:
            with open(log_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    if not line.strip():
                        continue

                    try:
                        event_data = json.loads(line)

                        # Extract fields
                        event_id = event_data.get('event_id')
                        event_type = event_data.get('event_type')
                        severity = event_data.get('severity', 'info')
                        user_id = event_data.get('user_id')
                        user_email = event_data.get('user_email')
                        ip_address = event_data.get('ip_address')
                        resource_type = event_data.get('resource_type')
                        resource_id = event_data.get('resource_id')
                        action = event_data.get('action')
                        details = event_data.get('details', {})
                        success = event_data.get('success', True)

                        # Save to database
                        database.log_audit_event(
                            event_id=event_id,
                            event_type=event_type,
                            severity=severity,
                            user_id=user_id,
                            user_email=user_email,
                            ip_address=ip_address,
                            resource_type=resource_type,
                            resource_id=resource_id,
                            action=action,
                            details=details,
                            success=success
                        )

                        total_migrated += 1

                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing line {line_num} in {log_file.name}: {e}")
                    except Exception as e:
                        logger.error(f"Error migrating line {line_num} in {log_file.name}: {e}")

            logger.info(f"✓ Processed {log_file.name}")

        except Exception as e:
            logger.error(f"Error reading {log_file.name}: {e}")

    logger.info(f"✓ Migrated {total_migrated} audit log entries to database")
    return total_migrated


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting audit log migration from files to SQLite")
    logger.info("=" * 60)

    count = migrate_audit_logs()

    logger.info("=" * 60)
    logger.info(f"Migration complete! Migrated {count} audit log entries")
    logger.info("You can now safely delete the audit_logs folder")
    logger.info("=" * 60)
