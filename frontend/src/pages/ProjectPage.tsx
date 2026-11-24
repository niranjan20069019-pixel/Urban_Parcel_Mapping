import { useState, useCallback, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { Upload, RefreshCw, Map } from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import {
  projectsApi, featuresApi, parcelsApi, gnssApi, imageryApi,
} from '@/services/api';
import MapContainer from '@/maps/MapContainer';
import LayerControl from '@/components/LayerControl';
import FeatureInfo from '@/components/FeatureInfo';
import ParcelEditor from '@/components/ParcelEditor';
import UploadDialog from '@/components/UploadDialog';
import PipelineControls from '@/components/PipelineControls';
import { defaultVisibility, LayerVisibility } from '@/maps/layers';
import { geometryToFeatureCollection, computeBBox } from '@/utils/geometry';
import type { Project, Parcel, GeoJsonFeatureCollection, GeoJsonGeometry, GeoJsonFeature } from '@/types';

export default function ProjectPage() {
  const { id } = useParams<{ id: string }>();
  const projectId = Number(id);

  const { data: project, refetch: refetchProject } = useApi(
    () => projectsApi.get(projectId),
    [projectId]
  );

  const { data: buildings, refetch: refetchBuildings } = useApi(
    () => featuresApi.geojson(projectId, 'buildings'),
    [projectId]
  );

  const { data: roads, refetch: refetchRoads } = useApi(
    () => featuresApi.geojson(projectId, 'roads'),
    [projectId]
  );

  const { data: landuse, refetch: refetchLanduse } = useApi(
    () => featuresApi.geojson(projectId, 'landuse'),
    [projectId]
  );

  const { data: boundaries, refetch: refetchBoundaries } = useApi(
    () => featuresApi.geojson(projectId, 'boundaries'),
    [projectId]
  );

  const [oldParcels, setOldParcels] = useState<GeoJsonFeatureCollection | undefined>();
  const [aiParcels, setAiParcels] = useState<GeoJsonFeatureCollection | undefined>();
  const [gnssFc, setGnssFc] = useState<GeoJsonFeatureCollection | undefined>();

  const loadParcels = useCallback(async () => {
    try {
      const parcels = await parcelsApi.list(projectId);
      const old: GeoJsonFeature[] = [];
      const ai: GeoJsonFeature[] = [];
      for (const p of parcels) {
        const feat: GeoJsonFeature = {
          type: 'Feature',
          geometry: p.geom_json,
          properties: { id: p.id, area: p.area, confidence: p.confidence, status: p.status },
        };
        if (p.status === 'old') old.push(feat);
        else if (['ai_generated', 'surveyor_edited', 'gnss_validated'].includes(p.status)) ai.push(feat);
      }
      setOldParcels(old.length ? { type: 'FeatureCollection', features: old } : undefined);
      setAiParcels(ai.length ? { type: 'FeatureCollection', features: ai } : undefined);
    } catch {
      // no parcels yet
    }
  }, [projectId]);

  const loadGnss = useCallback(async () => {
    try {
      const pts = await gnssApi.points(projectId);
      const fc: GeoJsonFeatureCollection = {
        type: 'FeatureCollection',
        features: pts.map((p) => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [p.longitude, p.latitude] },
          properties: { id: p.id, point_id: p.point_id, accuracy: p.accuracy, source: p.source },
        })),
      };
      setGnssFc(fc.features.length ? fc : undefined);
    } catch {
      // no gnss
    }
  }, [projectId]);

  const loadAll = useCallback(() => {
    loadParcels();
    loadGnss();
    refetchBuildings();
    refetchRoads();
    refetchLanduse();
    refetchBoundaries();
  }, [loadParcels, loadGnss, refetchBuildings, refetchRoads, refetchLanduse, refetchBoundaries]);

  useEffect(() => { loadAll(); }, [projectId]);

  const [vis, setVis] = useState<LayerVisibility>(defaultVisibility);
  const [selectedFeature, setSelectedFeature] = useState<GeoJSON.Feature | null>(null);
  const [editingParcel, setEditingParcel] = useState<Parcel | null>(null);
  const [showUpload, setShowUpload] = useState(false);

  const onSelectFeature = useCallback((feat: GeoJSON.Feature) => {
    const props = feat.properties ?? {};
    if (props.status && ['old', 'ai_generated', 'surveyor_edited'].includes(props.status)) {
      setSelectedFeature(feat);
    } else {
      setSelectedFeature(feat);
    }
  }, []);

  return (
    <div style={rootStyle}>
      <div style={toolbarStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Map size={18} color="#89b4fa" />
          <span style={{ fontWeight: 600, fontSize: 14 }}>{project?.name ?? 'Loading…'}</span>
          {project && (
            <span style={{ fontSize: 11, color: '#71717a', padding: '2px 8px', background: '#27272a', borderRadius: 8 }}>
              {project.status}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <PipelineControls projectId={projectId} onStatusChange={loadAll} />
          <button onClick={() => setShowUpload(true)} style={toolbarBtn}>
            <Upload size={14} /> Upload
          </button>
          <button onClick={loadAll} style={toolbarBtn}>
            <RefreshCw size={14} />
          </button>
        </div>
      </div>

      <div style={workspaceStyle}>
        <div style={leftSidebarStyle}>
          <LayerControl vis={vis} onChange={setVis} />
        </div>

        <div style={mapStyle}>
          <MapContainer
            vis={vis}
            data={{
              buildings,
              roads,
              landuse,
              boundaries,
              oldParcels,
              aiParcels,
              surveyorParcels: aiParcels,
              gnssPoints: gnssFc,
            }}
            onSelectFeature={onSelectFeature}
          />
        </div>

        {(selectedFeature || editingParcel) && (
          <div style={rightPanelStyle}>
            {editingParcel ? (
              <ParcelEditor
                parcel={editingParcel}
                onAccept={() => { setEditingParcel(null); loadAll(); }}
                onReject={() => { setEditingParcel(null); loadAll(); }}
                onClose={() => setEditingParcel(null)}
              />
            ) : selectedFeature ? (
              <FeatureInfo
                projectId={projectId}
                feature={selectedFeature}
                onEdit={(p) => { setEditingParcel(p); setSelectedFeature(null); }}
                onAccept={(p) => { loadAll(); setSelectedFeature(null); }}
                onReject={(p) => { loadAll(); setSelectedFeature(null); }}
                onClose={() => setSelectedFeature(null)}
              />
            ) : null}
          </div>
        )}
      </div>

      {showUpload && (
        <UploadDialog
          projectId={projectId}
          onClose={() => setShowUpload(false)}
          onComplete={() => { setShowUpload(false); loadAll(); }}
        />
      )}
    </div>
  );
}

const rootStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', height: '100%',
};

const toolbarStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  padding: '8px 16px', background: '#1e1e2e', borderBottom: '1px solid #27272a',
  flexShrink: 0,
};

const toolbarBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '6px 12px', background: '#27272a', border: '1px solid #3f3f46',
  borderRadius: 6, color: '#e4e4ef', fontSize: 12, fontWeight: 500, cursor: 'pointer',
};

const workspaceStyle: React.CSSProperties = {
  flex: 1, display: 'flex', overflow: 'hidden',
};

const leftSidebarStyle: React.CSSProperties = {
  width: 170, padding: 8, flexShrink: 0, overflowY: 'auto',
};

const mapStyle: React.CSSProperties = {
  flex: 1, position: 'relative',
};

const rightPanelStyle: React.CSSProperties = {
  width: 260, padding: 8, flexShrink: 0, overflowY: 'auto',
};
