import { useEffect } from 'react';
import { X, Check, Ban, Clock } from 'lucide-react';
import { useApi } from '@/hooks/useApi';
import { parcelsApi } from '@/services/api';
import { formatArea, formatPerimeter, confidenceColor } from '@/utils/geometry';
import type { Parcel, Confidence, Recommendation, ParcelVersion } from '@/types';

interface Props {
  projectId: number;
  feature: GeoJSON.Feature;
  onEdit?: (parcel: Parcel) => void;
  onAccept?: (parcel: Parcel) => void;
  onReject?: (parcel: Parcel) => void;
  onClose: () => void;
}

export default function FeatureInfo({ projectId, feature, onEdit, onAccept, onReject, onClose }: Props) {
  const props = feature.properties ?? {};
  const parcelId: number | null = props.id ?? null;

  const { data: parcel, loading: loadingParcel } = useApi<Parcel>(
    () => parcelsApi.get(parcelId!),
    [parcelId]
  );

  const { data: confidence } = useApi<Confidence>(
    () => parcelsApi.confidence(parcelId!),
    [parcelId]
  );

  const { data: recs } = useApi(
    () => parcelsApi.recommendations(parcelId!),
    [parcelId]
  );

  const { data: versions } = useApi<ParcelVersion[]>(
    () => parcelsApi.versions(parcelId!),
    [parcelId]
  );

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Feature Details</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#71717a', cursor: 'pointer' }}>
          <X size={16} />
        </button>
      </div>

      <div style={sectionStyle}>
        <Row label="Type" value={feature.geometry?.type ?? 'Unknown'} />
        <Row label="Source" value={props.source ?? 'N/A'} />
        {parcelId && <Row label="Parcel ID" value={`#${parcelId}`} />}
        {props.area != null && <Row label="Area" value={formatArea(props.area)} />}
        {props.perimeter != null && <Row label="Perimeter" value={formatPerimeter(props.perimeter)} />}
        {props.confidence != null && (
          <Row
            label="Confidence"
            value={`${(props.confidence * 100).toFixed(0)}%`}
            color={confidenceColor(props.confidence)}
          />
        )}
        {parcel?.status && <Row label="Status" value={parcel.status.replace(/_/g, ' ')} />}
      </div>

      {confidence && (
        <div style={sectionStyle}>
          <div style={sectionTitle}>Confidence Breakdown</div>
          {Object.entries(confidence).map(([k, v]) => (
            <div key={k} style={{ marginBottom: 6 }}>
              <div style={{ fontSize: 11, color: '#a1a1aa', marginBottom: 2 }}>
                {k.replace(/_/g, ' ')}
              </div>
              <div style={barTrackStyle}>
                <div style={{ ...barFillStyle, width: `${(v as number) * 100}%`, background: confidenceColor(v as number) }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {recs?.recommendations && recs.recommendations.length > 0 && (
        <div style={sectionStyle}>
          <div style={sectionTitle}>Recommendations</div>
          {recs.recommendations.map((r: Recommendation) => (
            <div key={r.id} style={recStyle}>
              <span style={{ ...badgeStyle, background: r.priority === 'high' ? '#dc2626' : r.priority === 'medium' ? '#f97316' : '#22c55e' }}>
                {r.priority}
              </span>
              <span style={{ fontSize: 12, flex: 1 }}>{r.reason}</span>
            </div>
          ))}
        </div>
      )}

      {versions && versions.length > 0 && (
        <div style={sectionStyle}>
          <div style={sectionTitle}>Version History</div>
          {versions.map((v) => (
            <div key={v.id} style={{ fontSize: 12, padding: '4px 0', borderBottom: '1px solid #27272a', display: 'flex', justifyContent: 'space-between' }}>
              <span>v{v.version} — {v.status}</span>
              <span style={{ color: '#71717a' }}>{formatArea(v.area)}</span>
            </div>
          ))}
        </div>
      )}

      {parcel && (
        <div style={{ display: 'flex', gap: 6, padding: '8px 0' }}>
          <button onClick={() => onEdit?.(parcel)} style={btnStyle('#f97316')}>Edit</button>
          <button onClick={() => onAccept?.(parcel)} style={btnStyle('#22c55e')}>
            <Check size={14} /> Accept
          </button>
          <button onClick={() => onReject?.(parcel)} style={btnStyle('#ef4444')}>
            <Ban size={14} /> Reject
          </button>
        </div>
      )}
    </div>
  );
}

function Row({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '3px 0', fontSize: 12 }}>
      <span style={{ color: '#a1a1aa' }}>{label}</span>
      <span style={{ color: color ?? '#e4e4ef', fontWeight: 500 }}>{value}</span>
    </div>
  );
}

const panelStyle: React.CSSProperties = {
  background: '#1e1e2e',
  borderRadius: 8,
  padding: 12,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
  minWidth: 240,
  maxHeight: '100%',
  overflowY: 'auto',
};

const headerStyle: React.CSSProperties = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
};

const sectionStyle: React.CSSProperties = {
  display: 'flex',
  flexDirection: 'column',
  gap: 4,
};

const sectionTitle: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 600,
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  color: '#71717a',
  marginBottom: 4,
};

const barTrackStyle: React.CSSProperties = {
  height: 6,
  background: '#27272a',
  borderRadius: 3,
  overflow: 'hidden',
};

const barFillStyle: React.CSSProperties = {
  height: '100%',
  borderRadius: 3,
  transition: 'width 0.3s',
};

const recStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: 6,
  padding: '4px 0',
};

const badgeStyle: React.CSSProperties = {
  fontSize: 9,
  padding: '1px 5px',
  borderRadius: 3,
  fontWeight: 600,
  color: '#fff',
  textTransform: 'uppercase',
  flexShrink: 0,
};

const btnStyle = (bg: string): React.CSSProperties => ({
  flex: 1,
  padding: '6px 8px',
  background: bg,
  border: 'none',
  borderRadius: 4,
  color: '#fff',
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 4,
});
