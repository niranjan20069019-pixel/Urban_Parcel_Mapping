import type { GeoJsonGeometry, GeoJsonFeatureCollection, GeoJsonFeature } from '@/types';

export function geometryToFeatureCollection(
  geoms: GeoJsonGeometry[],
  properties: Record<string, any>[] = []
): GeoJsonFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: geoms.map((g, i) => ({
      type: 'Feature',
      geometry: g,
      properties: properties[i] ?? {},
    })),
  };
}

export function singleFeatureCollection(
  geom: GeoJsonGeometry,
  properties: Record<string, any> = {}
): GeoJsonFeatureCollection {
  return {
    type: 'FeatureCollection',
    features: [{ type: 'Feature', geometry: geom, properties }],
  };
}

export function computeBBox(geoms: GeoJsonGeometry[]): [number, number, number, number] {
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  for (const g of geoms) {
    const coords = flattenCoords(g);
    for (let i = 0; i < coords.length; i += 2) {
      if (coords[i] < minX) minX = coords[i];
      if (coords[i] > maxX) maxX = coords[i];
      if (coords[i + 1] < minY) minY = coords[i + 1];
      if (coords[i + 1] > maxY) maxY = coords[i + 1];
    }
  }
  return [minX, minY, maxX, maxY];
}

function flattenCoords(geom: GeoJsonGeometry): number[] {
  if (geom.type === 'Point') return geom.coordinates as number[];
  if (geom.type === 'MultiPoint' || geom.type === 'LineString')
    return (geom.coordinates as number[][]).flat();
  if (geom.type === 'MultiLineString' || geom.type === 'Polygon')
    return (geom.coordinates as number[][][]).flat(2);
  if (geom.type === 'MultiPolygon')
    return (geom.coordinates as number[][][][]).flat(3);
  if (geom.type === 'GeometryCollection')
    return geom.coordinates.map(flattenCoords).flat();
  return [];
}

export function formatArea(areaSqMeters: number): string {
  if (areaSqMeters >= 10_000) {
    return `${(areaSqMeters / 10_000).toFixed(2)} ha`;
  }
  return `${areaSqMeters.toFixed(1)} m²`;
}

export function formatPerimeter(meters: number): string {
  return `${meters.toFixed(1)} m`;
}

export function confidenceColor(confidence: number): string {
  if (confidence >= 0.8) return '#22c55e';
  if (confidence >= 0.6) return '#eab308';
  if (confidence >= 0.4) return '#f97316';
  return '#ef4444';
}

export function statusColor(status: string): string {
  const map: Record<string, string> = {
    old: '#94a3b8',
    ai_generated: '#3b82f6',
    surveyor_edited: '#eab308',
    gnss_validated: '#22c55e',
    final_validated: '#10b981',
  };
  return map[status] ?? '#6b7280';
}

export function changeTypeColor(type: string): string {
  const map: Record<string, string> = {
    unchanged: '#94a3b8',
    boundary_shift: '#f97316',
    subdivision: '#8b5cf6',
    merger: '#06b6d4',
    new: '#22c55e',
    removed: '#ef4444',
    conflict: '#dc2626',
    uncertain: '#eab308',
  };
  return map[type] ?? '#6b7280';
}

export function blobToDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
