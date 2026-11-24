"""Run the full processing pipeline from command line."""
import argparse
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


async def main():
    parser = argparse.ArgumentParser(description='Run urban cadastral pipeline')
    parser.add_argument('--project-id', type=int, required=True)
    parser.add_argument('--skip-inference', action='store_true')
    parser.add_argument('--skip-parcels', action='store_true')
    parser.add_argument('--skip-comparison', action='store_true')
    parser.add_argument('--demo', action='store_true', help='Use mock data')
    args = parser.parse_args()

    from app.db.database import SessionLocal
    from app.services import (
        inference_service,
        parcel_inference_service,
        topology_service,
        confidence_service,
        comparison_service,
        change_detection_service,
        recommendation_service,
    )

    async with SessionLocal() as db:
        if not args.skip_inference:
            print("Running AI inference...")
            result = await inference_service.orchestrate_full_pipeline(args.project_id)
            print(f"  Predictions: {result}")

        if not args.skip_parcels:
            print("Inferring parcels...")
            parcels_gdf = parcel_inference_service.infer_parcels(args.project_id, {})
            print(f"  Generated {len(parcels_gdf)} candidate parcels")

        print("Validating topology...")
        issues = await topology_service.validate_parcels(args.project_id)
        print(f"  Issues: {issues}")

        print("Calculating confidence...")
        # confidence calculated per-parcel on demand via confidence_service

        if not args.skip_comparison:
            print("Comparing old vs new...")
            # comparison requires old parcels loaded as GeoDataFrame

        print("Generating recommendations...")
        recs = await recommendation_service.generate_recommendations(db, args.project_id)
        print(f"  Generated {len(recs)} recommendations")

        print("Pipeline complete.")


if __name__ == '__main__':
    asyncio.run(main())
