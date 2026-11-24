import axios from 'axios';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectList,
  Dataset,
  RasterInfo,
  Building,
  Road,
  LanduseFeature,
  BoundaryEvidence,
  Parcel,
  ParcelVersion,
  Confidence,
  RecommendationList,
  ChangeClassification,
  GnssPoint,
  TopologyIssue,
  InferenceStatus,
  FeatureType,
  GeoJsonFeatureCollection,
  SurveyorStats,
  TopologyValidationResponse,
  UploadResponse,
} from '@/types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api/v1',
  timeout: 60_000,
});

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const msg = err.response?.data?.detail || err.message;
    return Promise.reject(new Error(msg));
  }
);

// ── Projects ──────────────────────────────────────────────
export const projectsApi = {
  list: () => api.get<ProjectList>('/projects').then((r) => r.data),
  get: (id: number) => api.get<Project>(`/projects/${id}`).then((r) => r.data),
  create: (data: ProjectCreate) =>
    api.post<Project>('/projects', data).then((r) => r.data),
  update: (id: number, data: ProjectUpdate) =>
    api.put<Project>(`/projects/${id}`, data).then((r) => r.data),
  remove: (id: number) => api.delete(`/projects/${id}`),
  summary: (id: number) =>
    api.get(`/projects/${id}/summary`).then((r) => r.data),
};

// ── Upload ────────────────────────────────────────────────
export const uploadApi = {
  raster: (projectId: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post<UploadResponse>('/upload/raster', form, {
        params: { project_id: projectId },
      })
      .then((r) => r.data);
  },
  vector: (projectId: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post<UploadResponse>('/upload/vector', form, {
        params: { project_id: projectId },
      })
      .then((r) => r.data);
  },
  gnss: (projectId: number, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return api
      .post<UploadResponse>('/upload/gnss', form, {
        params: { project_id: projectId },
      })
      .then((r) => r.data);
  },
  all: (projectId: number, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append('files', f));
    return api
      .post<UploadResponse[]>(`/upload/${projectId}/all`, form)
      .then((r) => r.data);
  },
};

// ── Imagery / Datasets ────────────────────────────────────
export const imageryApi = {
  datasets: (projectId: number) =>
    api.get<Dataset[]>(`/projects/${projectId}/datasets`).then((r) => r.data),
  rasterInfo: (datasetId: number) =>
    api
      .get<RasterInfo>(`/datasets/${datasetId}/info`)
      .then((r) => r.data),
  reproject: (datasetId: number, targetCrs: string) =>
    api
      .post(`/datasets/${datasetId}/reproject`, null, {
        params: { target_crs: targetCrs },
      })
      .then((r) => r.data),
  tiles: (datasetId: number) =>
    api.get(`/datasets/${datasetId}/tiles`).then((r) => r.data),
};

// ── Inference ─────────────────────────────────────────────
export const inferenceApi = {
  run: (projectId: number) =>
    api.post(`/projects/${projectId}/inference/run`).then((r) => r.data),
  runModel: (projectId: number, modelName: string) =>
    api
      .post(`/projects/${projectId}/inference/${modelName}`)
      .then((r) => r.data),
  status: (projectId: number) =>
    api
      .get<InferenceStatus>(`/projects/${projectId}/inference/status`)
      .then((r) => r.data),
  predictions: (projectId: number) =>
    api.get(`/projects/${projectId}/predictions`).then((r) => r.data),
};

// ── Features ──────────────────────────────────────────────
export const featuresApi = {
  buildings: (projectId: number) =>
    api
      .get<Building[]>(`/projects/${projectId}/buildings`)
      .then((r) => r.data),
  roads: (projectId: number) =>
    api.get<Road[]>(`/projects/${projectId}/roads`).then((r) => r.data),
  landuse: (projectId: number) =>
    api
      .get<LanduseFeature[]>(`/projects/${projectId}/landuse`)
      .then((r) => r.data),
  boundaries: (projectId: number) =>
    api
      .get<BoundaryEvidence[]>(`/projects/${projectId}/boundaries`)
      .then((r) => r.data),
  geojson: (projectId: number, featureType: FeatureType) =>
    api
      .get<GeoJsonFeatureCollection>(
        `/projects/${projectId}/features/${featureType}/geojson`
      )
      .then((r) => r.data),
};

// ── Parcels ───────────────────────────────────────────────
export const parcelsApi = {
  infer: (projectId: number) =>
    api.post(`/projects/${projectId}/parcels/infer`).then((r) => r.data),
  list: (projectId: number) =>
    api.get<Parcel[]>(`/projects/${projectId}/parcels`).then((r) => r.data),
  get: (parcelId: number) =>
    api.get<Parcel>(`/parcels/${parcelId}`).then((r) => r.data),
  edit: (
    parcelId: number,
    data: { geom_json: Record<string, any>; notes?: string; editor: string }
  ) =>
    api.put<Parcel>(`/parcels/${parcelId}/edit`, data).then((r) => r.data),
  accept: (parcelId: number, data?: { notes?: string; editor: string }) =>
    api.post<Parcel>(`/parcels/${parcelId}/accept`, data).then((r) => r.data),
  reject: (parcelId: number, data?: { notes?: string; editor: string }) =>
    api.post<Parcel>(`/parcels/${parcelId}/reject`, data).then((r) => r.data),
  versions: (parcelId: number) =>
    api
      .get<ParcelVersion[]>(`/parcels/${parcelId}/versions`)
      .then((r) => r.data),
  confidence: (parcelId: number) =>
    api
      .get<Confidence>(`/parcels/${parcelId}/confidence`)
      .then((r) => r.data),
  recommendations: (parcelId: number) =>
    api
      .get<RecommendationList>(`/parcels/${parcelId}/recommendations`)
      .then((r) => r.data),
};

// ── Comparison ────────────────────────────────────────────
export const comparisonApi = {
  run: (projectId: number) =>
    api.post(`/projects/${projectId}/compare`).then((r) => r.data),
  changes: (projectId: number) =>
    api
      .get<ChangeClassification[]>(`/projects/${projectId}/changes`)
      .then((r) => r.data),
  summary: (projectId: number) =>
    api
      .get(`/projects/${projectId}/changes/summary`)
      .then((r) => r.data),
};

// ── Validation ────────────────────────────────────────────
export const validationApi = {
  topology: (projectId: number) =>
    api
      .post<TopologyValidationResponse>(
        `/projects/${projectId}/validate/topology`
      )
      .then((r) => r.data),
  repair: (projectId: number) =>
    api
      .post(`/projects/${projectId}/validate/repair`)
      .then((r) => r.data),
  issues: (projectId: number) =>
    api
      .get<TopologyIssue[]>(`/projects/${projectId}/topology-issues`)
      .then((r) => r.data),
};

// ── GNSS ──────────────────────────────────────────────────
export const gnssApi = {
  points: (projectId: number) =>
    api
      .get<GnssPoint[]>(`/projects/${projectId}/gnss/points`)
      .then((r) => r.data),
  validate: (projectId: number) =>
    api.post(`/projects/${projectId}/gnss/validate`).then((r) => r.data),
  match: (projectId: number) =>
    api.post(`/projects/${projectId}/gnss/match`).then((r) => r.data),
};

// ── Surveyor ──────────────────────────────────────────────
export const surveyorApi = {
  queue: (projectId: number) =>
    api.get<Parcel[]>(`/projects/${projectId}/surveyor/queue`).then((r) => r.data),
  edit: (
    projectId: number,
    parcelId: number,
    data: { geom_json: Record<string, any>; notes?: string; editor: string }
  ) =>
    api
      .post<Parcel>(
        `/projects/${projectId}/surveyor/${parcelId}/edit`,
        data
      )
      .then((r) => r.data),
  accept: (projectId: number, parcelId: number) =>
    api
      .post<Parcel>(`/projects/${projectId}/surveyor/${parcelId}/accept`)
      .then((r) => r.data),
  reject: (projectId: number, parcelId: number) =>
    api
      .post<Parcel>(`/projects/${projectId}/surveyor/${parcelId}/reject`)
      .then((r) => r.data),
  fieldVerify: (projectId: number, parcelId: number) =>
    api
      .post<Parcel>(
        `/projects/${projectId}/surveyor/${parcelId}/field-verify`
      )
      .then((r) => r.data),
  stats: (projectId: number) =>
    api
      .get<SurveyorStats>(`/projects/${projectId}/surveyor/stats`)
      .then((r) => r.data),
};

// ── Export ────────────────────────────────────────────────
export const exportApi = {
  parcelsGeojson: (projectId: number) =>
    api
      .get(`/projects/${projectId}/export/parcels`, {
        responseType: 'blob',
      })
      .then((r) => r.data),
  featuresGeojson: (projectId: number, featureType: FeatureType) =>
    api
      .get(`/projects/${projectId}/export/features/${featureType}`, {
        responseType: 'blob',
      })
      .then((r) => r.data),
  csv: (projectId: number) =>
    api
      .get(`/projects/${projectId}/export/csv`, { responseType: 'blob' })
      .then((r) => r.data),
  full: (projectId: number) =>
    api
      .get(`/projects/${projectId}/export/full`, { responseType: 'blob' })
      .then((r) => r.data),
};

export default api;
