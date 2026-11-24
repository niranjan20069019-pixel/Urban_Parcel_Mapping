import { useState, useCallback, useRef } from 'react';
import { X, Upload, FileImage, FileText, MapPin } from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadApi } from '@/services/api';

interface Props {
  projectId: number;
  onClose: () => void;
  onComplete: () => void;
}

type FileType = 'raster' | 'vector' | 'gnss';

interface QueuedFile {
  file: File;
  type: FileType;
  progress: number;
  status: 'pending' | 'uploading' | 'done' | 'error';
  error?: string;
}

const ALLOWED: Record<FileType, { accept: string; label: string }> = {
  raster: { accept: '.tif,.tiff,.geotiff,.jp2', label: 'Raster (GeoTIFF, JP2)' },
  vector: { accept: '.shp,.geojson,.json,.gpkg,.kml', label: 'Vector (SHP, GeoJSON, GPKG)' },
  gnss: { accept: '.csv,.txt,.gpx,.xyz', label: 'GNSS (CSV, GPX, XYZ)' },
};

export default function UploadDialog({ projectId, onClose, onComplete }: Props) {
  const [files, setFiles] = useState<QueuedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);

  const addFiles = useCallback((newFiles: FileList | File[], type: FileType) => {
    const allowed = ALLOWED[type].accept.split(',').map((e) => e.trim().toLowerCase());
    const filtered = Array.from(newFiles).filter((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      return allowed.some((a) => a === ext || a === '*');
    });
    setFiles((prev) => [
      ...prev,
      ...filtered.map((f) => ({ file: f, type, progress: 0, status: 'pending' as const })),
    ]);
  }, []);

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files;
    const rasterExts = ['.tif', '.tiff', '.jp2'];
    const vecExts = ['.shp', '.geojson', '.json', '.gpkg', '.kml'];
    Array.from(dropped).forEach((f) => {
      const ext = '.' + f.name.split('.').pop()?.toLowerCase();
      if (rasterExts.includes(ext)) addFiles([f], 'raster');
      else if (vecExts.includes(ext)) addFiles([f], 'vector');
      else addFiles([f], 'gnss');
    });
  };

  const uploadAll = async () => {
    setUploading(true);
    let ok = 0;
    for (let i = 0; i < files.length; i++) {
      if (files[i].status !== 'pending') continue;
      setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, status: 'uploading', progress: 0 } : f));
      try {
        if (files[i].type === 'raster') await uploadApi.raster(projectId, files[i].file);
        else if (files[i].type === 'vector') await uploadApi.vector(projectId, files[i].file);
        else await uploadApi.gnss(projectId, files[i].file);
        setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, status: 'done', progress: 100 } : f));
        ok++;
      } catch (err: any) {
        setFiles((prev) => prev.map((f, idx) => idx === i ? { ...f, status: 'error', error: err.message } : f));
      }
    }
    if (ok > 0) {
      toast.success(`${ok} file(s) uploaded`);
      onComplete();
    }
    setUploading(false);
  };

  const pending = files.filter((f) => f.status === 'pending').length;
  const iconForType = (t: FileType) => {
    if (t === 'raster') return <FileImage size={14} color="#3b82f6" />;
    if (t === 'vector') return <FileText size={14} color="#22c55e" />;
    return <MapPin size={14} color="#f97316" />;
  };

  return (
    <div style={overlayStyle} onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div style={dialogStyle}>
        <div style={headerStyle}>
          <span style={{ fontWeight: 600 }}>Upload Files</span>
          <button onClick={onClose} style={closeBtn}><X size={16} /></button>
        </div>

        <div
          style={{ ...dropzoneStyle, borderColor: dragOver ? '#3b82f6' : '#3f3f46' }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
        >
          <Upload size={24} color="#71717a" />
          <span style={{ fontSize: 13, color: '#71717a' }}>
            Drag & drop files here or click to browse
          </span>
          <span style={{ fontSize: 11, color: '#52525b' }}>
            Supports GeoTIFF, Shapefile, GeoJSON, CSV, GPX
          </span>
        </div>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".tif,.tiff,.geotiff,.jp2,.shp,.geojson,.json,.gpkg,.kml,.csv,.txt,.gpx,.xyz"
          style={{ display: 'none' }}
          onChange={(e) => {
            if (!e.target.files) return;
            Array.from(e.target.files).forEach((f) => {
              const ext = '.' + f.name.split('.').pop()?.toLowerCase();
              if (['.tif', '.tiff', '.jp2'].includes(ext)) addFiles([f], 'raster');
              else if (['.shp', '.geojson', '.gpkg', '.kml'].includes(ext)) addFiles([f], 'vector');
              else addFiles([f], 'gnss');
            });
          }}
        />

        <div style={{ display: 'flex', gap: 6 }}>
          {(['raster', 'vector', 'gnss'] as FileType[]).map((t) => (
            <label key={t} style={typeBtnStyle}>
              {iconForType(t)}
              {ALLOWED[t].label.split('(')[0].trim()}
              <input
                type="file"
                multiple
                accept={ALLOWED[t].accept}
                style={{ display: 'none' }}
                onChange={(e) => e.target.files && addFiles(e.target.files, t)}
              />
            </label>
          ))}
        </div>

        {files.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 160, overflowY: 'auto' }}>
            {files.map((f, i) => (
              <div key={i} style={fileRowStyle}>
                {iconForType(f.type)}
                <span style={{ flex: 1, fontSize: 12, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {f.file.name}
                </span>
                {f.status === 'pending' && <span style={{ color: '#71717a', fontSize: 11 }}>queued</span>}
                {f.status === 'uploading' && <span style={{ color: '#3b82f6', fontSize: 11 }}>uploading…</span>}
                {f.status === 'done' && <span style={{ color: '#22c55e', fontSize: 11 }}>✓</span>}
                {f.status === 'error' && <span style={{ color: '#ef4444', fontSize: 11 }} title={f.error}>✗</span>}
              </div>
            ))}
          </div>
        )}

        <button
          onClick={uploadAll}
          disabled={pending === 0 || uploading}
          style={{ ...uploadBtnStyle, opacity: pending === 0 || uploading ? 0.5 : 1 }}
        >
          {uploading ? 'Uploading…' : `Upload ${pending} file(s)`}
        </button>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
};

const dialogStyle: React.CSSProperties = {
  background: '#1e1e2e', borderRadius: 10, padding: 20, width: 480,
  display: 'flex', flexDirection: 'column', gap: 12, color: '#e4e4ef',
};

const headerStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
};

const closeBtn: React.CSSProperties = {
  background: 'none', border: 'none', color: '#71717a', cursor: 'pointer',
};

const dropzoneStyle: React.CSSProperties = {
  border: '2px dashed #3f3f46', borderRadius: 8, padding: 32,
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
  cursor: 'pointer', transition: 'border-color .2s',
};

const typeBtnStyle: React.CSSProperties = {
  flex: 1, padding: '8px 6px', background: '#27272a', border: '1px solid #3f3f46',
  borderRadius: 6, color: '#a1a1aa', fontSize: 11, cursor: 'pointer',
  display: 'flex', alignItems: 'center', gap: 4, justifyContent: 'center',
};

const fileRowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 6, padding: '6px 8px',
  background: '#27272a', borderRadius: 4,
};

const uploadBtnStyle: React.CSSProperties = {
  padding: '10px', background: '#3b82f6', border: 'none', borderRadius: 6,
  color: '#fff', fontWeight: 600, fontSize: 13, cursor: 'pointer',
};
