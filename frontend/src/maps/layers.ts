import type { LayerSpecification } from 'maplibre-gl';
import type { GeoJsonFeatureCollection } from '@/types';

export interface LayerVisibility {
  orthophoto: boolean;
  buildings: boolean;
  roads: boolean;
  landuse: boolean;
  boundaries: boolean;
  oldParcels: boolean;
  aiParcels: boolean;
  surveyorParcels: boolean;
  gnssPoints: boolean;
  changes: boolean;
}

export const defaultVisibility: LayerVisibility = {
  orthophoto: false,
  buildings: true,
  roads: true,
  landuse: false,
  boundaries: false,
  oldParcels: true,
  aiParcels: true,
  surveyorParcels: true,
  gnssPoints: true,
  changes: false,
};

export const LAYER_DEFINITIONS: { id: string; source: string; layer: LayerSpecification }[] = [
  {
    id: 'landuse-fill',
    source: 'landuse',
    layer: {
      id: 'landuse-fill',
      type: 'fill',
      source: 'landuse',
      paint: {
        'fill-color': [
          'match', ['get', 'landuse_class'],
          'residential', '#3b82f6',
          'commercial', '#f97316',
          'industrial', '#6b7280',
          'agricultural', '#22c55e',
          'forest', '#166534',
          'water', '#0ea5e9',
          'road', '#a1a1aa',
          'open_space', '#86efac',
          '#6b7280',
        ],
        'fill-opacity': 0.3,
      },
    },
  },
  {
    id: 'landuse-outline',
    source: 'landuse',
    layer: {
      id: 'landuse-outline',
      type: 'line',
      source: 'landuse',
      paint: {
        'line-color': '#6b7280',
        'line-width': 0.5,
      },
    },
  },
  {
    id: 'buildings-fill',
    source: 'buildings',
    layer: {
      id: 'buildings-fill',
      type: 'fill',
      source: 'buildings',
      paint: {
        'fill-color': '#f97316',
        'fill-opacity': 0.5,
      },
    },
  },
  {
    id: 'buildings-outline',
    source: 'buildings',
    layer: {
      id: 'buildings-outline',
      type: 'line',
      source: 'buildings',
      paint: {
        'line-color': '#ea580c',
        'line-width': 1,
      },
    },
  },
  {
    id: 'roads-line',
    source: 'roads',
    layer: {
      id: 'roads-line',
      type: 'line',
      source: 'roads',
      layout: { 'line-cap': 'round', 'line-join': 'round' },
      paint: {
        'line-color': '#9ca3af',
        'line-width': 2,
      },
    },
  },
  {
    id: 'boundaries-line',
    source: 'boundaries',
    layer: {
      id: 'boundaries-line',
      type: 'line',
      source: 'boundaries',
      paint: {
        'line-color': '#ef4444',
        'line-width': 1.5,
        'line-dasharray': [4, 3],
      },
    },
  },
  {
    id: 'old-parcels-outline',
    source: 'oldParcels',
    layer: {
      id: 'old-parcels-outline',
      type: 'line',
      source: 'oldParcels',
      paint: {
        'line-color': '#3b82f6',
        'line-width': 1.5,
      },
    },
  },
  {
    id: 'old-parcels-fill',
    source: 'oldParcels',
    layer: {
      id: 'old-parcels-fill',
      type: 'fill',
      source: 'oldParcels',
      paint: {
        'fill-color': '#3b82f6',
        'fill-opacity': 0.06,
      },
    },
  },
  {
    id: 'ai-parcels-outline',
    source: 'aiParcels',
    layer: {
      id: 'ai-parcels-outline',
      type: 'line',
      source: 'aiParcels',
      paint: {
        'line-color': '#22c55e',
        'line-width': 2,
      },
    },
  },
  {
    id: 'ai-parcels-fill',
    source: 'aiParcels',
    layer: {
      id: 'ai-parcels-fill',
      type: 'fill',
      source: 'aiParcels',
      paint: {
        'fill-color': '#22c55e',
        'fill-opacity': 0.08,
      },
    },
  },
  {
    id: 'surveyor-parcels-outline',
    source: 'surveyorParcels',
    layer: {
      id: 'surveyor-parcels-outline',
      type: 'line',
      source: 'surveyorParcels',
      paint: {
        'line-color': '#eab308',
        'line-width': 2.5,
      },
    },
  },
  {
    id: 'gnss-points',
    source: 'gnssPoints',
    layer: {
      id: 'gnss-points',
      type: 'circle',
      source: 'gnssPoints',
      paint: {
        'circle-radius': 5,
        'circle-color': '#ef4444',
        'circle-stroke-color': '#fff',
        'circle-stroke-width': 1,
      },
    },
  },
  {
    id: 'changes-fill',
    source: 'changes',
    layer: {
      id: 'changes-fill',
      type: 'fill',
      source: 'changes',
      paint: {
        'fill-color': '#ef4444',
        'fill-opacity': 0.25,
      },
    },
  },
  {
    id: 'changes-outline',
    source: 'changes',
    layer: {
      id: 'changes-outline',
      type: 'line',
      source: 'changes',
      paint: {
        'line-color': '#dc2626',
        'line-width': 2,
      },
    },
  },
];

export function buildSourceData(
  vis: LayerVisibility,
  data: {
    buildings?: GeoJsonFeatureCollection | null;
    roads?: GeoJsonFeatureCollection | null;
    landuse?: GeoJsonFeatureCollection | null;
    boundaries?: GeoJsonFeatureCollection | null;
    oldParcels?: GeoJsonFeatureCollection | null;
    aiParcels?: GeoJsonFeatureCollection | null;
    surveyorParcels?: GeoJsonFeatureCollection | null;
    gnssPoints?: GeoJsonFeatureCollection | null;
    changes?: GeoJsonFeatureCollection | null;
  }
): Record<string, GeoJsonFeatureCollection> {
  const sources: Record<string, GeoJsonFeatureCollection> = {};
  if (vis.buildings && data.buildings) sources.buildings = data.buildings;
  if (vis.roads && data.roads) sources.roads = data.roads;
  if (vis.landuse && data.landuse) sources.landuse = data.landuse;
  if (vis.boundaries && data.boundaries) sources.boundaries = data.boundaries;
  if (vis.oldParcels && data.oldParcels) sources.oldParcels = data.oldParcels;
  if (vis.aiParcels && data.aiParcels) sources.aiParcels = data.aiParcels;
  if (vis.surveyorParcels && data.surveyorParcels) sources.surveyorParcels = data.surveyorParcels;
  if (vis.gnssPoints && data.gnssPoints) sources.gnssPoints = data.gnssPoints;
  if (vis.changes && data.changes) sources.changes = data.changes;
  return sources;
}
