#!/usr/bin/env python3
"""
context-router.py: Smart context routing for PR-triggered area updates

Analyzes git diffs and determines which area context skills need updating.
Follows the pattern from doc_router.py for consistency.

USAGE:
    python3 scripts/context-router.py \\
        --base-ref origin/master \\
        --head-ref origin/feature-branch \\
        --output .ci-artifacts/routing-report.json

INTEGRATION:
    - Called by GitHub Actions (_context-update.yml)
    - Uses area-config.yml for routing rules
    - Outputs JSON report for downstream consumption
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple
import yaml
import fnmatch


class ContextRouter:
    """Routes changed files to affected area contexts."""

    def __init__(self, config_path: str = ".context/area-config.yml"):
        """Initialize router with area configuration."""
        self.config_path = Path(config_path)
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config not found: {config_path}")

        with open(self.config_path) as f:
            self.config = yaml.safe_load(f)

        self.areas = self.config.get("areas", {})
        self.settings = self.config.get("settings", {})
        self.routing_settings = self.settings.get("routing", {})

    def get_changed_files(self, base_ref: str, head_ref: str) -> List[str]:
        """Get list of changed files between two refs."""
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", base_ref, head_ref],
                capture_output=True,
                text=True,
                check=True
            )
            files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
            return files
        except subprocess.CalledProcessError as e:
            print(f"Error getting changed files: {e}", file=sys.stderr)
            print(f"stderr: {e.stderr}", file=sys.stderr)
            raise

    def matches_glob(self, file_path: str, glob_pattern: str) -> bool:
        """Check if file path matches glob pattern."""
        # Handle ** (recursive) and * (single level)
        return fnmatch.fnmatch(file_path, glob_pattern)

    def score_file(self, file_path: str, area_name: str) -> float:
        """Calculate confidence score for file belonging to area."""
        area_config = self.areas.get(area_name, {})
        if not area_config.get("enabled", True):
            return 0.0

        confidence = 0.0

        # Check glob patterns
        globs = area_config.get("globs", [])
        for glob_pattern in globs:
            if self.matches_glob(file_path, glob_pattern):
                confidence += 0.5
                break  # Only count once per file

        # Check detector patterns (content-based)
        detectors = area_config.get("detectors", [])
        if detectors and Path(file_path).exists():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    for detector in detectors:
                        pattern = detector.get("pattern", "")
                        weight = detector.get("weight", 0.2)
                        if re.search(pattern, content):
                            confidence += weight
            except (UnicodeDecodeError, IOError):
                # Skip binary files or unreadable files
                pass

        # Check excludes
        excludes = area_config.get("excludes", [])
        for exclude_pattern in excludes:
            if self.matches_glob(file_path, exclude_pattern):
                confidence = 0.0  # Excluded files get zero score
                break

        return min(confidence, 1.0)  # Cap at 1.0

    def route_changes(self, changed_files: List[str]) -> Dict[str, Dict]:
        """Route changed files to affected areas."""
        affected_areas = {}

        for file_path in changed_files:
            # Score file against all areas
            file_scores = {}
            for area_name in self.areas.keys():
                score = self.score_file(file_path, area_name)
                if score > 0:
                    file_scores[area_name] = score

            # Add to affected areas if above threshold
            threshold = self.routing_settings.get("update_threshold", 0.3)
            for area_name, score in file_scores.items():
                if score >= threshold:
                    if area_name not in affected_areas:
                        affected_areas[area_name] = {
                            "confidence": score,
                            "files": [],
                            "priority": self.areas[area_name].get("priority", 99)
                        }
                    affected_areas[area_name]["files"].append({
                        "path": file_path,
                        "confidence": score
                    })
                    # Update max confidence for area
                    affected_areas[area_name]["confidence"] = max(
                        affected_areas[area_name]["confidence"],
                        score
                    )

        # Cap at max_areas_per_pr
        max_areas = self.routing_settings.get("max_areas_per_pr", 3)
        if len(affected_areas) > max_areas:
            # Sort by confidence descending, then by priority ascending
            sorted_areas = sorted(
                affected_areas.items(),
                key=lambda x: (-x[1]["confidence"], x[1]["priority"])
            )
            affected_areas = dict(sorted_areas[:max_areas])

        return affected_areas

    def generate_report(
        self,
        base_ref: str,
        head_ref: str,
        changed_files: List[str],
        affected_areas: Dict[str, Dict]
    ) -> Dict:
        """Generate routing report."""
        return {
            "metadata": {
                "base_ref": base_ref,
                "head_ref": head_ref,
                "total_files": len(changed_files),
                "affected_areas_count": len(affected_areas),
                "timestamp": subprocess.run(
                    ["date", "+%Y-%m-%dT%H:%M:%S%z"],
                    capture_output=True,
                    text=True
                ).stdout.strip()
            },
            "changed_files": changed_files,
            "affected_areas": list(affected_areas.keys()),
            "area_details": affected_areas,
            "recommendations": {
                "should_update": len(affected_areas) > 0,
                "areas_to_update": list(affected_areas.keys()),
                "total_files_affected": sum(
                    len(area["files"]) for area in affected_areas.values()
                )
            }
        }


def main():
    parser = argparse.ArgumentParser(
        description="Route git changes to affected area contexts"
    )
    parser.add_argument(
        "--base-ref",
        required=True,
        help="Base git ref (e.g., origin/master)"
    )
    parser.add_argument(
        "--head-ref",
        required=True,
        help="Head git ref (e.g., origin/feature-branch)"
    )
    parser.add_argument(
        "--output",
        default=".ci-artifacts/routing-report.json",
        help="Output file for routing report"
    )
    parser.add_argument(
        "--config",
        default=".context/area-config.yml",
        help="Path to area configuration file"
    )

    args = parser.parse_args()

    # Initialize router
    try:
        router = ContextRouter(config_path=args.config)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    # Get changed files
    try:
        changed_files = router.get_changed_files(args.base_ref, args.head_ref)
        print(f"Found {len(changed_files)} changed files")
    except Exception as e:
        print(f"Error analyzing changes: {e}", file=sys.stderr)
        sys.exit(1)

    # Route changes
    affected_areas = router.route_changes(changed_files)
    print(f"Affected areas: {list(affected_areas.keys())}")

    # Generate report
    report = router.generate_report(
        base_ref=args.base_ref,
        head_ref=args.head_ref,
        changed_files=changed_files,
        affected_areas=affected_areas
    )

    # Write output
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Report written to: {output_path}")

    # Print summary
    print("\n" + "=" * 50)
    print("ROUTING SUMMARY")
    print("=" * 50)
    print(f"Base ref: {args.base_ref}")
    print(f"Head ref: {args.head_ref}")
    print(f"Changed files: {len(changed_files)}")
    print(f"Affected areas: {len(affected_areas)}")
    if affected_areas:
        print("\nAreas to update:")
        for area_name, details in affected_areas.items():
            print(f"  - {area_name}: {len(details['files'])} files (confidence: {details['confidence']:.2f})")
    else:
        print("\nNo areas affected (no context updates needed)")
    print("=" * 50)


if __name__ == "__main__":
    main()
