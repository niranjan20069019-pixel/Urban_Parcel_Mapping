# Surveyor Workflow

Surveyors are the final authority. AI output is candidate evidence only.

## State machine

```
OLD  →  AI_GENERATED  →  SURVEYOR_EDITED  →  GNSS_VALIDATED  →  FINAL_VALIDATED
                                ↕
                          SURVEYOR_REVIEW  (accept → next, reject → AI_GENERATED)
```

`ParcelStatus` is defined in `backend/app/db/models.py`.

## Typical flow

1. **Review queue** — `GET /api/v1/surveyor/queue` lists parcels in
   `AI_GENERATED`/`SURVEYOR_EDITED` order, with confidence and unresolved
   change types.
2. **Inspect** — the WebGIS shows the orthophoto plus overlay layers: old
   boundaries, AI candidates, boundary evidence, GNSS points, change mask.
3. **Check evidence** — confidence breakdown, recommendation reasons, and
   change metrics for the parcel (IoU, displacement, change_type).
4. **Decide**:
   - `accept` → parcel moves toward FINAL_VALIDATED (validation record
     written with validator name);
   - `edit` → surveyor edits vertices; every edit is a `surveyor_edits` row
     with old/new geometry, editor, and optional notes; status becomes
     `SURVEYOR_EDITED`;
   - `reject` → status returns to `AI_GENERATED` with a validation record;
   - `field-verify` → flags the parcel, adds to the field queue.
5. **Notes** — free-text annotations attached to the parcel.
6. **GNSS validation** — match points; high agreement plus accuracy within
   threshold promotes the parcel to `GNSS_VALIDATED`.
7. **Final validation** — surveyor confirms → `FINAL_VALIDATED`.
8. **Export** — only validated layers, or all layers with their status
   attribute, to GeoJSON/GPKG/Shapefile/CSV.

## Editing

`ParcelEditor` (frontend) draws/moves vertices on the map; `PUT
/api/v1/parcels/{id}/edit` persists the new polygon and records a
SurveyorEdit. Geometry is repaired (`buffer(0)`) if invalid. Version history
is retained via `parcels` version field and `surveyor_edits` list.

## Auditability

Every transition writes a `validation` row (validator, type, status, notes,
timestamp). Surveyor edits preserve the previous geometry, so the chain
`OLD → AI → edited → validated` is fully reconstructable.

## Legal stance

`FINAL_VALIDATED` means *validated by the surveyor with the available
evidence* for this project's internal workflow. Whether the output satisfies
your jurisdiction's legal cadastral requirements is a separate, legal
question — the system does not and cannot certify ownership.