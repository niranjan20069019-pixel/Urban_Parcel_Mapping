export type ProjectStatus = 'draft' | 'processing' | 'completed';

export interface Project {
  id: number;
  name: string;
  description: string | null;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface ProjectList {
  projects: Project[];
  total: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  status?: ProjectStatus;
}

export interface Dataset {
  id: number;
  project_id: number;
  file_name: string;
  dataset_type: string;
  bbox_wgs84: number[] | null;
  created_at: string;
}

export interface RasterInfo {
  width: number;
  height: number;
  bands: number;
  crs: string;
  resolution: { x: number; y: number };
  bounds: number[];
  nodata: number | null;
}

export interface Building {
  id: number;
  area: number;
  perimeter: number;
  confidence: number;
  height: number | null;
  geom_json: GeoJsonGeometry;
}

export interface Road {
  id: number;
  road_class: string;
  width: number | null;
  length: number;
  confidence: number;
  geom_json: GeoJsonGeometry;
  centerline_json: GeoJsonGeometry | null;
}

export interface LanduseFeature {
  id: number;
  landuse_class: string;
  area: number;
  confidence: number;
  geom_json: GeoJsonGeometry;
}

export interface BoundaryEvidence {
  id: number;
  boundary_type: string;
  confidence: number;
  geom_json: GeoJsonGeometry;
}

export type ParcelStatus =
  | 'old'
  | 'ai_generated'
  | 'surveyor_edited'
  | 'gnss_validated'
  | 'final_validated';

export interface Parcel {
  id: number;
  project_id: number;
  version: number;
  status: ParcelStatus;
  area: number;
  perimeter: number;
  confidence: number;
  change_type: string | null;
  geom_json: GeoJsonGeometry;
  metadata: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface ParcelVersion {
  id: number;
  version: number;
  status: ParcelStatus;
  area: number;
  geom_json: GeoJsonGeometry;
  created_at: string;
}

export interface Confidence {
  ai_agreement: number;
  gis_agreement: number;
  boundary_evidence: number;
  gnss_agreement: number;
  topology_validity: number;
}

export type RecommendationAction =
  | 'accept_preliminary'
  | 'surveyor_review'
  | 'gnss_verification'
  | 'field_survey'
  | 'boundary_review'
  | 'topology_repair'
  | 'investigate_subdivision'
  | 'investigate_merger'
  | 'investigate_new_parcel';

export type Priority = 'high' | 'medium' | 'low';

export interface Recommendation {
  id: number;
  parcel_id: number;
  action: RecommendationAction;
  priority: Priority;
  reason: string;
  evidence_json: Record<string, any> | null;
  created_at: string;
}

export interface RecommendationList {
  recommendations: Recommendation[];
  counts_by_priority: Record<string, number>;
}

export type ChangeType =
  | 'unchanged'
  | 'boundary_shift'
  | 'subdivision'
  | 'merger'
  | 'new'
  | 'removed'
  | 'conflict'
  | 'uncertain';

export interface ChangeClassification {
  old_parcel_id: number;
  new_parcel_id: number;
  iou: number;
  area_difference: number;
  centroid_distance: number;
  boundary_displacement: number;
  hausdorff_distance: number;
  change_type: ChangeType;
}

export interface GnssPoint {
  id: number;
  point_id: string;
  latitude: number;
  longitude: number;
  height: number | null;
  accuracy: number | null;
  crs: string;
  source: string | null;
  created_at: string;
}

export interface TopologyIssue {
  id: number;
  issue_type: string;
  description: string;
  severity: string;
  resolved: boolean;
  geom_json: GeoJsonGeometry | null;
}

export interface SurveyorEdit {
  id: number;
  parcel_id: number;
  editor: string;
  geom_json: GeoJsonGeometry;
  notes: string | null;
  created_at: string;
}

export interface GeoJsonGeometry {
  type: string;
  coordinates: any;
}

export interface GeoJsonFeature {
  type: 'Feature';
  geometry: GeoJsonGeometry | null;
  properties: Record<string, any>;
}

export interface GeoJsonFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJsonFeature[];
}

export type FeatureType = 'buildings' | 'roads' | 'landuse' | 'boundaries';

export interface UploadResponse {
  dataset_id: number;
  file_name: string;
  dataset_type: string;
  message: string;
}

export interface InferenceStatus {
  running: boolean;
  current_model: string | null;
  progress: number;
  message: string;
  completed_models: string[];
}

export interface SurveyorStats {
  total_queued: number;
  reviewed: number;
  accepted: number;
  rejected: number;
  edited: number;
}

export interface TopologyValidationResponse {
  project_id: number;
  issues_found: number;
  issues: TopologyIssue[];
}
