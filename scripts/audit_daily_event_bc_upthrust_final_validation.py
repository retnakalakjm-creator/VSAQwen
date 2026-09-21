from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from audit.daily_event_bc_upthrust_final_validation import (  # noqa: E402
    DEFAULT_SEQUENCE_LOOKBACK_BARS,
    build_bc_upthrust_final_validation_audit,
    load_bc_upthrust_final_sources,
    write_bc_upthrust_final_validation_audit,
)


def _default_output(input_dir: Path) -> Path:
    return (
        Path("reports/daily-events/bc-upthrust-final-validation")
        / input_dir.parent.name
        / input_dir.name
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the final bounded robustness and behavior-sequence "
            "validation for the frozen BUYING_CLIMAX exhaustion and "
            "structural UPTHRUST candidates."
        )
    )
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument(
        "--sequence-lookback-bars",
        type=int,
        default=DEFAULT_SEQUENCE_LOOKBACK_BARS,
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args(argv)

    sources = load_bc_upthrust_final_sources(args.input_dir)
    audit = build_bc_upthrust_final_validation_audit(
        sources,
        sequence_lookback_bars=args.sequence_lookback_bars,
    )
    paths = write_bc_upthrust_final_validation_audit(
        audit,
        args.output_dir or _default_output(args.input_dir),
    )

    print(
        json.dumps(
            {
                "audit_id": audit.audit_id,
                "requested_symbol_count": audit.requested_symbol_count,
                "evaluated_target_count": audit.evaluated_target_count,
                "bc_candidate_count": audit.bc_candidate_count,
                "ut_candidate_count": audit.ut_candidate_count,
                "same_bar_overlap_count": audit.same_bar_overlap_count,
                "bc_only_count": audit.bc_only_count,
                "ut_only_count": audit.ut_only_count,
                "candidate_union_count": audit.candidate_union_count,
                "era_count": audit.era_count,
                "sequence_lookback_bars": audit.sequence_lookback_bars,
                "current_behavior_mapping_collapsed": (
                    audit.current_behavior_mapping_collapsed
                ),
                "symbol_row_count": len(audit.symbol_rows),
                "symbol_summary_row_count": len(
                    audit.symbol_summary_rows
                ),
                "era_row_count": len(audit.era_rows),
                "partition_row_count": len(audit.partition_rows),
                "transition_row_count": len(audit.transition_rows),
                "transition_offset_row_count": len(
                    audit.transition_offset_rows
                ),
                "transition_era_row_count": len(
                    audit.transition_era_rows
                ),
                "behavior_mapping_row_count": len(
                    audit.behavior_mapping_rows
                ),
                "source_lineage": asdict(audit.source_lineage),
                "output_files": paths.as_dict(),
                "is_actionable": False,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
