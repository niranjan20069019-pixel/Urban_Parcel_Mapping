# Parcel Inference

## What is a parcel?

A parcel is a **legal/administrative construct**, not a visual object. The
system respects these hard boundaries:

- **Building ≠ parcel.** A footprint is evidence about where a building
  stands, sometimes near an edge. It is never the boundary.
- **Road ≠ parcel.** Roads partition space, but the parcel edge usu. lies on
  the road centreline or property line, not the pavement edge.
- **Wall / fence ≠ legal boundary.** Visible boundary evidence suggests where
  an edge *may* be; it must be confirmed against land records and GNSS.
- **AI prediction ≠ legal cadastral record.** AI output is premesis for
  surveyor verification, never a substitute for it.

## Evidence inputs

`ParcelInferenceService` accepts:

| Input | Role |
|-------|------|
| Existing parcels | Region of interest + strongest prior |
| Building polygons | Building density/arrangement hints at subdivision |
| Road / pathway polygons | Space partition; road edges delimit blocks |
| Boundary evidence | Visible walls/fences/hedges as edge candidates |
| Land-use regions | Development pattern (residential vs bare) |
| DSM / DTM / nDSM | Terrain and structure height |
| GNSS points | Verified ground control for corners/edges |

## Combination strategy (deterministic, v1)

1. Derive the **study area** from existing parcels if present, else the
   union of detected buildings buffered slightly.
2. **Split the area along roads** (`shapely.ops.split` on the road union):
   roads physically separate parcels.
3. Refine with **boundary evidence**: split regions along detected
   wall/fence lines where they run across a region.
4. Estimate subdivisions from **building arrangement** where evidence is weak
   (blocks, arrangement count).
5. Score each candidate with `_compute_confidence` from the weighted factors:
   existing parcel agreement, road separation, building density, boundary
   evidence, GNSS support, land-use consistency, area plausibility.
6. **Filter**: drop slivers under a minimum area; repair geometries.

## Confidence metadata

Every candidate records a `reasoning` dict: source
(`existing_parcel_subdivision` vs `new_candidate`), whether roads split the
region, building/boundary counts, GNSS presence, land-use match. This makes
the candidate auditable.

## Future: GAT/GATv2

`GATParcelAdapter` represents parcels as graph nodes with
adjacency / shared-boundary / road edges to *learn* parcel relationships once
labelled parcel graphs exist. It does not replace the deterministic engine;
it complements it after enough validated parcels are available.

## Never forget

The output of this stage — and of every earlier stage — is `AI_GENERATED`,
a **candidate** with a confidence score. It becomes a parcel only after
surveyor review and GNSS validation.