"""
Alert Validation Tracker

Tracks predictive alert accuracy and manages false positive/true positive analysis.
Part of PROJECT VANGUARD Phase A - Validation & Monitoring.

Usage:
    python scripts/monitoring/alert_validation_tracker.py --validate
    python scripts/monitoring/alert_validation_tracker.py --report
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class AlertValidationTracker:
    """
    Track and analyze predictive alert accuracy.

    Maintains a validation database to track:
    - True Positives: Alerts that correctly predicted actual issues
    - False Positives: Alerts that did not lead to actual issues
    - False Negatives: Issues that occurred without prior alerts
    - True Negatives: Normal operation without alerts (baseline)
    """

    def __init__(self, validation_db_path: str = "data/alert_validation.json"):
        self.validation_db_path = Path(validation_db_path)
        self.validation_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load_database()

    def _load_database(self) -> dict:
        """Load validation database from disk."""
        if self.validation_db_path.exists():
            try:
                with open(self.validation_db_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load validation database: {e}")
                return self._create_empty_database()
        return self._create_empty_database()

    def _create_empty_database(self) -> dict:
        """Create empty validation database structure."""
        return {
            "alerts": [],
            "incidents": [],
            "validation_entries": [],
            "statistics": {
                "total_alerts": 0,
                "true_positives": 0,
                "false_positives": 0,
                "false_negatives": 0,
                "accuracy": 0.0,
                "precision": 0.0,
                "recall": 0.0,
                "f1_score": 0.0,
            },
            "created_at": datetime.utcnow().isoformat(),
            "last_updated": datetime.utcnow().isoformat(),
        }

    def _save_database(self) -> None:
        """Save validation database to disk."""
        try:
            self.data["last_updated"] = datetime.utcnow().isoformat()
            with open(self.validation_db_path, "w") as f:
                json.dump(self.data, f, indent=2, default=str)
            logger.info(f"Validation database saved to {self.validation_db_path}")
        except Exception as e:
            logger.error(f"Failed to save validation database: {e}")

    def record_alert(
        self,
        alert_id: str,
        service_name: str,
        metric_type: str,
        predicted_breach_time: str | None,
        confidence: float,
        severity: str,
        metadata: dict | None = None,
    ) -> None:
        """
        Record a new predictive alert.

        Args:
            alert_id: Unique alert identifier
            service_name: Service being monitored
            metric_type: Type of metric (error_rate, cpu_utilization, etc.)
            predicted_breach_time: When breach is predicted to occur
            confidence: Alert confidence score (0.0-1.0)
            severity: Alert severity (critical, high, medium, low)
            metadata: Additional alert context
        """
        alert_entry = {
            "alert_id": alert_id,
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "metric_type": metric_type,
            "predicted_breach_time": predicted_breach_time,
            "confidence": confidence,
            "severity": severity,
            "metadata": metadata or {},
            "status": "pending_validation",
            "outcome": None,
            "validated_at": None,
            "validation_notes": None,
        }

        self.data["alerts"].append(alert_entry)
        self.data["statistics"]["total_alerts"] += 1
        self._save_database()

        logger.info(
            f"Recorded alert {alert_id}: {service_name}/{metric_type} "
            f"(confidence={confidence:.2f}, severity={severity})",
        )

    def record_incident(
        self,
        incident_id: str,
        service_name: str,
        metric_type: str,
        occurred_at: str,
        severity: str,
        description: str,
        related_alert_id: str | None = None,
    ) -> None:
        """
        Record an actual incident that occurred.

        Args:
            incident_id: Unique incident identifier
            service_name: Service that experienced the incident
            metric_type: Type of metric that failed
            occurred_at: When the incident occurred
            severity: Incident severity
            description: Description of what happened
            related_alert_id: Alert ID if this incident was predicted
        """
        incident_entry = {
            "incident_id": incident_id,
            "timestamp": datetime.utcnow().isoformat(),
            "service_name": service_name,
            "metric_type": metric_type,
            "occurred_at": occurred_at,
            "severity": severity,
            "description": description,
            "related_alert_id": related_alert_id,
            "was_predicted": related_alert_id is not None,
        }

        self.data["incidents"].append(incident_entry)
        self._save_database()

        logger.info(
            f"Recorded incident {incident_id}: {service_name}/{metric_type} (predicted={related_alert_id is not None})",
        )

    def validate_alert(self, alert_id: str, outcome: str, notes: str | None = None) -> None:
        """
        Validate an alert's accuracy.

        Args:
            alert_id: Alert to validate
            outcome: Validation outcome (true_positive, false_positive)
            notes: Additional validation notes
        """
        if outcome not in ["true_positive", "false_positive"]:
            raise ValueError(f"Invalid outcome: {outcome}. Must be 'true_positive' or 'false_positive'")

        # Find and update alert
        alert_found = False
        for alert in self.data["alerts"]:
            if alert["alert_id"] == alert_id:
                alert["status"] = "validated"
                alert["outcome"] = outcome
                alert["validated_at"] = datetime.utcnow().isoformat()
                alert["validation_notes"] = notes
                alert_found = True
                break

        if not alert_found:
            logger.error(f"Alert {alert_id} not found for validation")
            return

        # Update statistics
        if outcome == "true_positive":
            self.data["statistics"]["true_positives"] += 1
        elif outcome == "false_positive":
            self.data["statistics"]["false_positives"] += 1

        # Recalculate metrics
        self._recalculate_statistics()
        self._save_database()

        logger.info(f"Validated alert {alert_id} as {outcome}")

    def _recalculate_statistics(self) -> None:
        """Recalculate accuracy statistics."""
        stats = self.data["statistics"]
        tp = stats["true_positives"]
        fp = stats["false_positives"]
        fn = stats["false_negatives"]

        # Precision: TP / (TP + FP)
        if (tp + fp) > 0:
            stats["precision"] = tp / (tp + fp)
        else:
            stats["precision"] = 0.0

        # Recall: TP / (TP + FN)
        if (tp + fn) > 0:
            stats["recall"] = tp / (tp + fn)
        else:
            stats["recall"] = 0.0

        # F1 Score: 2 * (Precision * Recall) / (Precision + Recall)
        if (stats["precision"] + stats["recall"]) > 0:
            stats["f1_score"] = 2 * (stats["precision"] * stats["recall"]) / (stats["precision"] + stats["recall"])
        else:
            stats["f1_score"] = 0.0

        # Accuracy: (TP + TN) / Total (approximation without TN tracking)
        total_validated = tp + fp + fn
        if total_validated > 0:
            stats["accuracy"] = tp / total_validated
        else:
            stats["accuracy"] = 0.0

    def detect_false_negatives(self, lookback_hours: int = 24) -> list[dict]:
        """
        Detect false negatives: incidents without prior alerts.

        Args:
            lookback_hours: How far back to check for alerts before incident

        Returns:
            List of potential false negative incidents
        """
        false_negatives = []
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

        for incident in self.data["incidents"]:
            if incident["was_predicted"]:
                continue

            incident_time = datetime.fromisoformat(incident["occurred_at"])

            # Check if there was any alert for this service/metric in lookback window
            had_prior_alert = False
            for alert in self.data["alerts"]:
                alert_time = datetime.fromisoformat(alert["timestamp"])
                if (
                    alert["service_name"] == incident["service_name"]
                    and alert["metric_type"] == incident["metric_type"]
                    and alert_time <= incident_time
                    and alert_time >= cutoff_time
                ):
                    had_prior_alert = True
                    break

            if not had_prior_alert:
                false_negatives.append(incident)
                self.data["statistics"]["false_negatives"] += 1

        if false_negatives:
            self._recalculate_statistics()
            self._save_database()

        return false_negatives

    def generate_validation_report(self, output_path: str | None = None) -> dict:
        """
        Generate comprehensive validation report.

        Args:
            output_path: Optional path to save report

        Returns:
            Report dictionary
        """
        stats = self.data["statistics"]

        # Calculate false positive rate
        total_alerts = stats["total_alerts"]
        fp_rate = (stats["false_positives"] / total_alerts * 100) if total_alerts > 0 else 0.0

        # Get pending alerts
        pending_alerts = [a for a in self.data["alerts"] if a["status"] == "pending_validation"]

        # Get recent true positives
        recent_tps = [a for a in self.data["alerts"] if a["outcome"] == "true_positive"][-10:]

        # Get recent false positives
        recent_fps = [a for a in self.data["alerts"] if a["outcome"] == "false_positive"][-10:]

        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "summary": {
                "total_alerts": total_alerts,
                "true_positives": stats["true_positives"],
                "false_positives": stats["false_positives"],
                "false_negatives": stats["false_negatives"],
                "false_positive_rate": fp_rate,
                "pending_validation": len(pending_alerts),
            },
            "metrics": {
                "accuracy": stats["accuracy"],
                "precision": stats["precision"],
                "recall": stats["recall"],
                "f1_score": stats["f1_score"],
            },
            "targets": {
                "target_fp_rate": 10.0,
                "current_fp_rate": fp_rate,
                "meets_target": fp_rate <= 10.0,
                "target_precision": 0.90,
                "current_precision": stats["precision"],
                "meets_precision_target": stats["precision"] >= 0.90,
            },
            "pending_alerts": pending_alerts,
            "recent_true_positives": recent_tps,
            "recent_false_positives": recent_fps,
            "recommendations": self._generate_recommendations(stats, fp_rate),
        }

        if output_path:
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w") as f:
                json.dump(report, f, indent=2, default=str)
            logger.info(f"Validation report saved to {output_file}")

        return report

    def _generate_recommendations(self, stats: dict, fp_rate: float) -> list[str]:
        """Generate tuning recommendations based on current performance."""
        recommendations = []

        if fp_rate > 10.0:
            recommendations.append(
                f"False positive rate ({fp_rate:.1f}%) exceeds target (10%). "
                "Consider increasing confidence_threshold or z_score_threshold "
                "in predictive_alerts.py",
            )

        if stats["precision"] < 0.90:
            recommendations.append(
                f"Precision ({stats['precision']:.2f}) below target (0.90). "
                "Increase threshold parameters to reduce false positives.",
            )

        if stats["recall"] < 0.70:
            recommendations.append(
                f"Recall ({stats['recall']:.2f}) below target (0.70). "
                "Decrease threshold parameters to catch more true issues.",
            )

        if stats["total_alerts"] < 10:
            recommendations.append(
                "Insufficient data for reliable statistics. Continue monitoring to accumulate more validation data.",
            )

        if not recommendations:
            recommendations.append("System performance meets targets. Continue monitoring.")

        return recommendations

    def export_for_tuning(self, output_path: str) -> None:
        """
        Export data in format suitable for algorithm tuning.

        Args:
            output_path: Path to save tuning data
        """
        tuning_data = {
            "validated_alerts": [a for a in self.data["alerts"] if a["status"] == "validated"],
            "incidents": self.data["incidents"],
            "statistics": self.data["statistics"],
            "exported_at": datetime.utcnow().isoformat(),
        }

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w") as f:
            json.dump(tuning_data, f, indent=2, default=str)

        logger.info(f"Tuning data exported to {output_file}")


def main():
    """Main entry point for alert validation tracking."""
    import argparse

    parser = argparse.ArgumentParser(description="Alert Validation Tracker")
    parser.add_argument("--validate", action="store_true", help="Run validation analysis")
    parser.add_argument("--report", action="store_true", help="Generate validation report")
    parser.add_argument("--output", type=str, help="Output file for report", default="data/validation_report.json")
    parser.add_argument("--detect-fn", action="store_true", help="Detect false negatives")
    parser.add_argument(
        "--lookback-hours", type=int, default=24, help="Hours to look back for false negative detection",
    )

    args = parser.parse_args()

    tracker = AlertValidationTracker()

    if args.detect_fn:
        logger.info("Detecting false negatives...")
        false_negatives = tracker.detect_false_negatives(args.lookback_hours)
        print(f"\nFound {len(false_negatives)} potential false negatives:")
        for fn in false_negatives:
            print(f"  - {fn['service_name']}/{fn['metric_type']} at {fn['occurred_at']}")

    if args.validate:
        logger.info("Running validation analysis...")
        # This would integrate with actual alert and incident data
        # For now, just generate a report
        args.report = True

    if args.report:
        logger.info("Generating validation report...")
        report = tracker.generate_validation_report(args.output)

        print("\n" + "=" * 80)
        print("PREDICTIVE ALERT VALIDATION REPORT")
        print("=" * 80)
        print(f"\nGenerated: {report['generated_at']}")
        print(f"\nSummary:")
        print(f"  Total Alerts: {report['summary']['total_alerts']}")
        print(f"  True Positives: {report['summary']['true_positives']}")
        print(f"  False Positives: {report['summary']['false_positives']}")
        print(f"  False Negatives: {report['summary']['false_negatives']}")
        print(f"  False Positive Rate: {report['summary']['false_positive_rate']:.1f}%")
        print(f"  Pending Validation: {report['summary']['pending_validation']}")

        print(f"\nPerformance Metrics:")
        print(f"  Accuracy: {report['metrics']['accuracy']:.2%}")
        print(f"  Precision: {report['metrics']['precision']:.2%}")
        print(f"  Recall: {report['metrics']['recall']:.2%}")
        print(f"  F1 Score: {report['metrics']['f1_score']:.2%}")

        print(f"\nTarget Achievement:")
        print(f"  FP Rate Target: {report['targets']['target_fp_rate']:.1f}%")
        print(f"  Meets FP Target: {report['targets']['meets_target']}")
        print(f"  Precision Target: {report['targets']['target_precision']:.2%}")
        print(f"  Meets Precision Target: {report['targets']['meets_precision_target']}")

        print(f"\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"  {i}. {rec}")

        print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
