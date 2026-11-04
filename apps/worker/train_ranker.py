"""Offline recommendation model training entrypoint."""
from __future__ import annotations
import argparse
import json
from packages.database.sessions import SessionLocal
from packages.recommendations.training import promote_ranker, train_and_register_ranker


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and register a candidate JobSeeker ranker")
    parser.add_argument("--min-rows", type=int, default=100)
    parser.add_argument("--promote-model-id", type=int)
    parser.add_argument("--minimum-auc", type=float, default=0.60)
    args = parser.parse_args()
    with SessionLocal() as db:
        if args.promote_model_id:
            model = promote_ranker(db, args.promote_model_id, minimum_auc=args.minimum_auc)
            result = {"status": "active", "model_id": model.id,
                      "model_version": model.model_version, "metrics": model.metrics}
        else:
            result = train_and_register_ranker(db, min_rows=args.min_rows)
        print(json.dumps(result, default=str, indent=2))


if __name__ == "__main__":
    main()
