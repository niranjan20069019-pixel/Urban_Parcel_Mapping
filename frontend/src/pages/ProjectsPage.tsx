import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, ChevronRight, Layers } from 'lucide-react';
import toast from 'react-hot-toast';
import { useApi } from '@/hooks/useApi';
import { projectsApi } from '@/services/api';
import type { Project, ProjectCreate } from '@/types';

export default function ProjectsPage() {
  const navigate = useNavigate();
  const { data, loading, error, refetch } = useApi(() => projectsApi.list(), []);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await projectsApi.create({ name: name.trim(), description: description.trim() || undefined });
      toast.success('Project created');
      setName('');
      setDescription('');
      setShowCreate(false);
      refetch();
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <div style={containerStyle}>
      <div style={topBarStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Layers size={20} color="#89b4fa" />
          <h1 style={{ fontSize: 18, fontWeight: 700 }}>Projects</h1>
        </div>
        <button onClick={() => setShowCreate(!showCreate)} style={createBtn}>
          <Plus size={14} /> New Project
        </button>
      </div>

      {showCreate && (
        <div style={formStyle}>
          <input
            placeholder="Project name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            style={inputStyle}
            autoFocus
          />
          <input
            placeholder="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            style={inputStyle}
          />
          <div style={{ display: 'flex', gap: 6 }}>
            <button onClick={handleCreate} style={submitBtn} disabled={creating || !name.trim()}>
              {creating ? 'Creating…' : 'Create'}
            </button>
            <button onClick={() => setShowCreate(false)} style={cancelBtn}>Cancel</button>
          </div>
        </div>
      )}

      {loading && <div style={{ padding: 24, color: '#71717a' }}>Loading projects…</div>}
      {error && <div style={{ padding: 24, color: '#ef4444' }}>{error}</div>}

      {data && data.projects.length === 0 && (
        <div style={{ padding: 48, textAlign: 'center', color: '#52525b' }}>
          <Layers size={40} style={{ margin: '0 auto 12px', opacity: 0.4 }} />
          <p style={{ fontSize: 14 }}>No projects yet. Create one to get started.</p>
        </div>
      )}

      {data && data.projects.length > 0 && (
        <div style={tableStyle}>
          {data.projects.map((p: Project) => (
            <button
              key={p.id}
              onClick={() => navigate(`/projects/${p.id}`)}
              style={rowStyle}
            >
              <div style={{ flex: 1, textAlign: 'left' }}>
                <div style={{ fontWeight: 600, fontSize: 13 }}>{p.name}</div>
                <div style={{ fontSize: 11, color: '#71717a', marginTop: 2 }}>
                  {p.description || 'No description'}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{
                  fontSize: 11, padding: '2px 8px', borderRadius: 10,
                  background: p.status === 'completed' ? '#22c55e22' : p.status === 'processing' ? '#f9731622' : '#3b82f622',
                  color: p.status === 'completed' ? '#22c55e' : p.status === 'processing' ? '#f97316' : '#3b82f6',
                  fontWeight: 500,
                }}>
                  {p.status}
                </span>
                <ChevronRight size={16} color="#52525b" />
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

const containerStyle: React.CSSProperties = {
  padding: '16px 24px', height: '100%', overflowY: 'auto',
  display: 'flex', flexDirection: 'column', gap: 12,
};

const topBarStyle: React.CSSProperties = {
  display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  paddingBottom: 8, borderBottom: '1px solid #27272a',
};

const createBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4,
  padding: '8px 14px', background: '#3b82f6', border: 'none',
  borderRadius: 6, color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const formStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 8, padding: 16,
  background: '#1e1e2e', borderRadius: 8,
};

const inputStyle: React.CSSProperties = {
  padding: '8px 12px', background: '#27272a', border: '1px solid #3f3f46',
  borderRadius: 6, color: '#e4e4ef', fontSize: 13, fontFamily: 'Inter, sans-serif',
};

const submitBtn: React.CSSProperties = {
  padding: '8px 16px', background: '#3b82f6', border: 'none',
  borderRadius: 6, color: '#fff', fontSize: 12, fontWeight: 600, cursor: 'pointer',
};

const cancelBtn: React.CSSProperties = {
  padding: '8px 16px', background: '#27272a', border: '1px solid #3f3f46',
  borderRadius: 6, color: '#a1a1aa', fontSize: 12, cursor: 'pointer',
};

const tableStyle: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 4,
};

const rowStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '12px 16px', background: '#1e1e2e', border: 'none',
  borderRadius: 8, color: '#e4e4ef', cursor: 'pointer', width: '100%',
  textAlign: 'left', transition: 'background .15s',
};
