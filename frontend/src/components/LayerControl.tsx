import { Eye, EyeOff } from 'lucide-react';
import { LayerVisibility, defaultVisibility } from '@/maps/layers';

interface Props {
  vis: LayerVisibility;
  onChange: (vis: LayerVisibility) => void;
}

const LAYERS: { key: keyof LayerVisibility; label: string }[] = [
  { key: 'orthophoto', label: 'Orthophoto' },
  { key: 'buildings', label: 'Buildings' },
  { key: 'roads', label: 'Roads' },
  { key: 'landuse', label: 'Land Use' },
  { key: 'boundaries', label: 'Boundaries' },
  { key: 'oldParcels', label: 'Old Parcels' },
  { key: 'aiParcels', label: 'AI Parcels' },
  { key: 'surveyorParcels', label: 'Surveyor Parcels' },
  { key: 'gnssPoints', label: 'GNSS Points' },
  { key: 'changes', label: 'Changes / Conflicts' },
];

export default function LayerControl({ vis, onChange }: Props) {
  const toggle = (key: keyof LayerVisibility) => {
    onChange({ ...vis, [key]: !vis[key] });
  };

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>Layers</div>
      {LAYERS.map(({ key, label }) => (
        <button key={key} onClick={() => toggle(key)} style={rowStyle}>
          <span style={{ fontSize: 12 }}>{label}</span>
          {vis[key] ? (
            <Eye size={14} color="#22c55e" />
          ) : (
            <EyeOff size={14} color="#52525b" />
          )}
        </button>
      ))}
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  background: '#1e1e2e',
  borderRadius: 8,
  padding: 8,
  display: 'flex',
  flexDirection: 'column',
  gap: 2,
  minWidth: 160,
};

const headerStyle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.05em',
  color: '#71717a',
  padding: '4px 8px',
};

const rowStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  gap: 8,
  padding: '6px 8px',
  background: 'none',
  border: 'none',
  color: '#e4e4ef',
  cursor: 'pointer',
  borderRadius: 4,
  width: '100%',
  textAlign: 'left',
  fontSize: 13,
};
