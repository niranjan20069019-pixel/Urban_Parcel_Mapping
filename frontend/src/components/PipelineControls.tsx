import { useState } from 'react';
import {
  Play, GitCompare, AlertTriangle, Download, ChevronDown, Loader2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { inferenceApi, parcelsApi, comparisonApi, validationApi, exportApi } from '@/services/api';
import { blobToDownload } from '@/utils/geometry';

interface Props {
  projectId: number;
  onStatusChange?: () => void;
}

export default function PipelineControls({ projectId, onStatusChange }: Props) {
  const [loading, setLoading] = useState<string | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  const wrap = async (key: string, fn: () => Promise<void>) => {
    setLoading(key);
    try {
      await fn();
      onStatusChange?.();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(null);
    }
  };

  const runInference = () =>
    wrap('inference', async () => {
      await inferenceApi.run(projectId);
      toast.success('Inference started');
    });

  const runParcels = () =>
    wrap('parcels', async () => {
      await parcelsApi.infer(projectId);
      toast.success('Parcel inference started');
    });

  const compare = () =>
    wrap('compare', async () => {
      await comparisonApi.run(projectId);
      toast.success('Comparison complete');
    });

  const validateTopology = () =>
    wrap('topology', async () => {
      await validationApi.topology(projectId);
      toast.success('Topology validation complete');
    });

  const exportFile = async (type: 'parcels' | 'csv' | 'full') => {
    setExportOpen(false);
    await wrap(`export-${type}`, async () => {
      let blob: Blob;
      if (type === 'parcels') blob = await exportApi.parcelsGeojson(projectId);
      else if (type === 'csv') blob = await exportApi.csv(projectId);
      else blob = await exportApi.full(projectId);
      blobToDownload(blob, `project-${projectId}-${type}.zip`);
      toast.success('Export downloaded');
    });
  };

  const Spinner = ({ name }: { name: string }) =>
    loading === name ? <Loader2 size={14} className="animate-spin" /> : null;

  return (
    <div style={barStyle}>
      <button onClick={runInference} style={btnStyle} disabled={!!loading}>
        <Spinner name="inference" />
        <Play size={14} /> Run Inference
      </button>

      <button onClick={runParcels} style={btnStyle} disabled={!!loading}>
        <Spinner name="parcels" />
        <Play size={14} /> Parcel Inference
      </button>

      <button onClick={compare} style={btnStyle} disabled={!!loading}>
        <Spinner name="compare" />
        <GitCompare size={14} /> Compare
      </button>

      <button onClick={validateTopology} style={btnStyle} disabled={!!loading}>
        <Spinner name="topology" />
        <AlertTriangle size={14} /> Validate Topology
      </button>

      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setExportOpen(!exportOpen)}
          style={btnStyle}
          disabled={!!loading}
        >
          <Download size={14} /> Export <ChevronDown size={12} />
        </button>
        {exportOpen && (
          <div style={dropdownStyle}>
            <button onClick={() => exportFile('parcels')} style={dropItem}>Parcels GeoJSON</button>
            <button onClick={() => exportFile('csv')} style={dropItem}>CSV</button>
            <button onClick={() => exportFile('full')} style={dropItem}>Full Package</button>
          </div>
        )}
      </div>
    </div>
  );
}

const barStyle: React.CSSProperties = {
  display: 'flex', gap: 6, alignItems: 'center',
};

const btnStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '6px 12px', background: '#27272a', border: '1px solid #3f3f46',
  borderRadius: 6, color: '#e4e4ef', fontSize: 12, fontWeight: 500,
  cursor: 'pointer', whiteSpace: 'nowrap',
};

const dropdownStyle: React.CSSProperties = {
  position: 'absolute', top: '100%', right: 0, marginTop: 4,
  background: '#1e1e2e', border: '1px solid #3f3f46', borderRadius: 6,
  overflow: 'hidden', zIndex: 50, minWidth: 160,
};

const dropItem: React.CSSProperties = {
  display: 'block', width: '100%', padding: '8px 12px', background: 'none',
  border: 'none', color: '#e4e4ef', fontSize: 12, textAlign: 'left', cursor: 'pointer',
};
