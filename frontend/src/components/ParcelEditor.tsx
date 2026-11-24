import { useState } from 'react';
import { X, Check, Ban, MapPin } from 'lucide-react';
import { parcelsApi } from '@/services/api';
import toast from 'react-hot-toast';
import type { Parcel } from '@/types';

interface Props {
  parcel: Parcel;
  onAccept: (parcel: Parcel) => void;
  onReject: (parcel: Parcel) => void;
  onClose: () => void;
}

export default function ParcelEditor({ parcel, onAccept, onReject, onClose }: Props) {
  const [notes, setNotes] = useState('');
  const [fieldVerified, setFieldVerified] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleAccept = async () => {
    setLoading(true);
    try {
      const result = await parcelsApi.accept(parcel.id, { notes, editor: 'surveyor' });
      toast.success(`Parcel #${parcel.id} accepted`);
      onAccept(result);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      const result = await parcelsApi.reject(parcel.id, { notes, editor: 'surveyor' });
      toast.success(`Parcel #${parcel.id} rejected`);
      onReject(result);
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={panelStyle}>
      <div style={headerStyle}>
        <span style={{ fontWeight: 600, fontSize: 13 }}>Parcel Editor</span>
        <button onClick={onClose} style={{ background: 'none', border: 'none', color: '#71717a', cursor: 'pointer' }}>
          <X size={16} />
        </button>
      </div>

      <div style={sectionStyle}>
        <div style={{ fontSize: 12, color: '#a1a1aa' }}>Parcel #{parcel.id}</div>
        <div style={{ fontSize: 12 }}>
          Status:{' '}
          <span style={{ fontWeight: 500 }}>{parcel.status.replace(/_/g, ' ')}</span>
        </div>
        <div style={{ fontSize: 12 }}>
          Version: <span style={{ fontWeight: 500 }}>{parcel.version}</span>
        </div>
      </div>

      <div style={sectionStyle}>
        <div style={sectionTitle}>Boundary Comparison</div>
        <div style={{ fontSize: 12, color: '#a1a1aa', padding: '4px 0' }}>
          Old boundary: <span style={{ color: '#3b82f6' }}>blue outline</span>
        </div>
        <div style={{ fontSize: 12, color: '#a1a1aa', padding: '4px 0' }}>
          AI boundary: <span style={{ color: '#22c55e' }}>green outline</span>
        </div>
      </div>

      <div style={sectionStyle}>
        <label style={checkboxLabel}>
          <input
            type="checkbox"
            checked={fieldVerified}
            onChange={(e) => setFieldVerified(e.target.checked)}
            style={{ marginRight: 6 }}
          />
          <MapPin size={14} />
          Field Verified
        </label>
      </div>

      <div style={sectionStyle}>
        <div style={sectionTitle}>Notes</div>
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Add surveyor notes..."
          style={textareaStyle}
          rows={3}
        />
      </div>

      <div style={{ display: 'flex', gap: 6, paddingTop: 8 }}>
        <button onClick={handleAccept} style={btnStyle('#22c55e')} disabled={loading}>
          <Check size={14} /> Accept
        </button>
        <button onClick={handleReject} style={btnStyle('#ef4444')} disabled={loading}>
          <Ban size={14} /> Reject
        </button>
      </div>
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
  minWidth: 220,
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
  marginBottom: 2,
};

const checkboxLabel: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  fontSize: 12,
  cursor: 'pointer',
};

const textareaStyle: React.CSSProperties = {
  background: '#27272a',
  border: '1px solid #3f3f46',
  borderRadius: 4,
  color: '#e4e4ef',
  padding: '6px 8px',
  fontSize: 12,
  fontFamily: 'Inter, sans-serif',
  resize: 'vertical',
  width: '100%',
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
