import { useCallback, useMemo } from 'react';
import Map, { Source, Layer, MapLayerMouseEvent, NavigationControl, ScaleControl } from 'react-map-gl/maplibre';
import { useMap } from 'react-map-gl/maplibre';
import type { GeoJsonFeatureCollection } from '@/types';
import { LAYER_DEFINITIONS, buildSourceData, LayerVisibility } from './layers';

interface Props {
  vis: LayerVisibility;
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
  };
  orthophotoUrl?: string;
  onSelectFeature: (feature: GeoJSON.Feature) => void;
  initialViewState?: { longitude: number; latitude: number; zoom: number };
}

const INTERACTIVE_LAYERS = [
  'old-parcels-fill',
  'ai-parcels-fill',
  'old-parcels-outline',
  'ai-parcels-outline',
  'surveyor-parcels-outline',
  'buildings-fill',
  'landuse-fill',
];

export default function MapContainer({
  vis,
  data,
  orthophotoUrl,
  onSelectFeature,
  initialViewState = { longitude: 85.3096, latitude: 27.7103, zoom: 12 },
}: Props) {
  const sourceData = useMemo(() => buildSourceData(vis, data), [vis, data]);

  const handleClick = useCallback(
    (e: MapLayerMouseEvent) => {
      const feat = e.features?.[0] as GeoJSON.Feature | undefined;
      if (feat) onSelectFeature(feat);
    },
    [onSelectFeature]
  );

  const activeLayers = useMemo(
    () =>
      LAYER_DEFINITIONS.filter((l) => {
        if (l.source === 'oldParcels') return vis.oldParcels;
        if (l.source === 'aiParcels') return vis.aiParcels;
        if (l.source === 'surveyorParcels') return vis.surveyorParcels;
        if (l.source === 'gnssPoints') return vis.gnssPoints;
        if (l.source === 'changes') return vis.changes;
        return vis[l.source as keyof LayerVisibility];
      }),
    [vis]
  );

  return (
    <Map
      initialViewState={initialViewState}
      style={{ width: '100%', height: '100%' }}
      mapStyle={{
        version: 8,
        sources: {
          osm: {
            type: 'raster',
            tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
            attribution: '© OpenStreetMap',
            tileSize: 256,
          },
          ...(orthophotoUrl && vis.orthophoto
            ? { orthophoto: { type: 'raster', tiles: [orthophotoUrl], tileSize: 256 } }
            : {}),
        },
        layers: [
          { id: 'osm', type: 'raster', source: 'osm', minzoom: 0 },
          ...(orthophotoUrl && vis.orthophoto
            ? [{ id: 'orthophoto', type: 'raster' as const, source: 'orthophoto', minzoom: 14 }]
            : []),
        ],
      }}
      onClick={handleClick}
      interactiveLayerIds={INTERACTIVE_LAYERS}
    >
      <NavigationControl position="top-right" />
      <ScaleControl position="bottom-right" />
      {Object.entries(sourceData).map(([key, fc]) => (
        <Source key={key} id={key} type="geojson" data={fc}>
          {activeLayers
            .filter((l) => l.source === key)
            .map((l) => (
              <Layer key={l.id} {...l.layer} beforeId="osm" />
            ))}
        </Source>
      ))}
    </Map>
  );
}
