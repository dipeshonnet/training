export type Role = "admin" | "trainer" | "agent";
export type Office = "front" | "back";
export type Channel = "workflow" | "chat" | "voice";
export type Mode = "walkthrough" | "practice" | "assessment";
export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  banned?: boolean;
}
export interface Process {
  id: string;
  name: string;
  client: string;
  description: string;
}
export interface Batch {
  id: string;
  name: string;
  process_id: string;
  members: string[];
}
export interface Hotspot {
  id: string;
  label: string;
  type: "click" | "input";
  x: number;
  y: number;
  w: number;
  h: number;
  accepted: string[];
  correct: boolean;
  critical: boolean;
}
export interface Step {
  id: string;
  title: string;
  instructions: string;
  hint: string;
  assetId: string;
  critical: boolean;
  hotspots: Hotspot[];
}
export type CriterionKey =
  "procedure" | "resolution" | "compliance" | "communication";
export interface Criterion {
  key: CriterionKey;
  label: string;
  weight: number;
  guidance: string;
}
export interface ScenarioContent {
  title: string;
  office: Office;
  brief: string;
  reference: string;
  outcome: string;
  customerName: string;
  persona: string;
  opening: string;
  threshold: number;
  rubric: Criterion[];
  steps: Step[];
}
export interface Scenario {
  id: string;
  process_id: string;
  title: string;
  office: Office;
  draft_json?: string;
  draft_revision: number;
  published_version: number | null;
  updated_at: number;
  draft?: ScenarioContent;
}
export interface Assignment {
  id: string;
  user_id: string;
  batch_id: string | null;
  scenario_version_id: string;
  channels: Channel[];
  title: string;
  office: Office;
  version: number;
  process_id: string;
  process_name: string;
  user_name?: string;
  completedChannels: Channel[];
  completed: boolean;
  latestScore?: number;
}
export interface ActionEvent {
  id: string;
  request_id: string;
  step_id: string;
  hotspot_id: string | null;
  value: string | null;
  correct: number;
  critical: number;
  created_at: number;
}
export interface Turn {
  id: string;
  request_id: string;
  sequence: number;
  agent_text: string;
  customer_text: string | null;
  state: "pending" | "completed" | "failed";
  created_at: number;
}
export interface CriterionResult {
  key: CriterionKey;
  score: number;
  feedback: string;
  evidenceIds: string[];
}
export interface Assessment {
  score: number;
  passed: boolean;
  criticalPassed: boolean;
  criteria: CriterionResult[];
  strengths: string[];
  improvements: string[];
  elapsedSeconds: number;
}
export interface LearnerHotspot extends Omit<
  Hotspot,
  "accepted" | "correct" | "critical"
> {
  correct?: boolean;
}
export interface LearnerStep {
  id: string;
  title?: string;
  instructions?: string;
  hint?: string;
  assetId: string;
  hotspots: LearnerHotspot[];
}
export interface LearnerScenario {
  title: string;
  office: Office;
  brief: string;
  customerName: string;
  steps: LearnerStep[];
  version: number;
}
export interface Attempt {
  id: string;
  assignment_id: string;
  user_id: string;
  mode: Mode;
  channel: Channel;
  status: "active" | "submitted" | "approved" | "retry";
  current_step: number;
  started_at: number;
  submitted_at: number | null;
  result: Assessment | null;
  review_note: string | null;
  reviewed_at: number | null;
  title?: string;
  user_name?: string;
  process_id?: string;
  scenario?: LearnerScenario;
  reviewContext?: { reference: string; outcome: string; threshold: number };
  events?: ActionEvent[];
  turns?: Turn[];
}
export interface Overview {
  user: User;
  processes: Process[];
  batches: Batch[];
  scenarios: Scenario[];
  assignments: Assignment[];
  attempts: Attempt[];
  users: User[];
  aiConfigured: boolean;
}
