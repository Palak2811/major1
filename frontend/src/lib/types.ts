export type Role = "student" | "content_manager" | "admin";

export interface User {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  scopes: string[];
  is_active: boolean;
  has_password: boolean;
  google_linked: boolean;
  created_at: string;
}

export interface TokenOut {
  access_token: string;
  expires_in: number;
  user: User;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Profile {
  user_id: number;
  full_name: string;
  email: string;
  college: string;
  branch: string;
  graduation_year: number | null;
  target_role: string;
  target_company_ids: number[];
  dsa_score: number | null;
  csf_score: number | null;
  aptitude_score: number | null;
  coding_score: number | null;
  study_streak: number;
  topics_completed: number;
  weak_topics: string[];
  preferred_language: "python" | "cpp" | "java" | "javascript";
  resume_id: number | null;
  completeness: number;
}

export const AREAS = ["DSA", "DBMS", "OS", "CN", "OOP", "Aptitude", "HR", "General"] as const;
export type Area = (typeof AREAS)[number];

export interface Topic {
  id: number;
  name: string;
  slug: string;
  area: Area;
  description: string;
  parent_id: number | null;
  question_count: number;
}

export interface SkillWeights { dsa: number; oop: number; dbms: number; os: number; aptitude: number; hr: number }
export interface OAPattern {
  coding_questions: number;
  mcqs: number;
  duration_minutes: number;
  difficulty: Difficulty;
  frequent_topics: string[];
}
export interface ReadinessWeights {
  dsa: number; csf: number; coding: number; aptitude: number; interview: number; consistency: number;
}

export interface Company {
  id: number;
  name: string;
  slug: string;
  description: string;
  skill_weights: SkillWeights;
  oa_pattern: OAPattern;
  readiness_weights: ReadinessWeights | null;
  pattern_disclaimer: string;
  question_count: number;
}

export const QUESTION_TYPES = [
  "mcq", "multi_select", "numerical", "coding", "output_prediction", "sql", "debugging", "theory",
] as const;
export type QuestionType = (typeof QUESTION_TYPES)[number];
export type Difficulty = "easy" | "medium" | "hard";

export const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "MCQ",
  multi_select: "Multi-select",
  numerical: "Numerical",
  coding: "Coding",
  output_prediction: "Output prediction",
  sql: "SQL",
  debugging: "Debugging",
  theory: "Theory",
};

export interface Question {
  id: number;
  type: QuestionType;
  title: string;
  body: string;
  difficulty: Difficulty;
  topic: { id: number; name: string; slug: string; area: Area } | null;
  companies: { id: number; name: string; slug: string }[];
  options: { id: string; text: string }[];
  meta: Record<string, unknown>;
  status: "draft" | "published" | "archived" | "review" | "rejected";
  source: "manual" | "ai";
  created_at: string;
  updated_at: string;
  answer: Record<string, unknown> | null;
  explanation: string | null;
}

export interface Stats {
  users: number;
  students: number;
  topics: number;
  questions_published: number;
  questions_draft: number;
  companies: number;
}

/* ---------------- Phase 2 ---------------- */

export type Answer = { selected?: string[]; value?: number; text?: string; code?: string; language?: string };

export interface TeachingBlock {
  kind: "explanation" | "worked_example";
  title: string;
  body: string;
  grounded: boolean;
  provider: string;
  sources: { document_id: number; title: string }[];
}

export interface AnswerResult {
  correct: boolean;
  score: number;
  gradable: boolean;
  judged_by: "auto" | "heuristic" | "pending";
  feedback: string;
  time_ms: number;
  response: Answer;
  answer: Record<string, unknown>;
  explanation: string;
}

export interface StudySession {
  id: number;
  status: "in_progress" | "completed";
  stage: "question" | "followup" | "quiz" | "confidence" | "done";
  topic: { id: number; name: string; area: Area } | null;
  mastery_before: number | null;
  target_difficulty: Difficulty;
  question: Question;
  explanation: TeachingBlock | null;
  worked_example: TeachingBlock | null;
  followup: Question | null;
  quiz: Question[];
  answers: Record<string, AnswerResult>;
  confidence: number | null;
  result: { changes: { skill_id: number; skill: string; before: number; after: number }[]; score: number; max_score: number } | null;
}

export interface SkillNode {
  id: number;
  name: string;
  area: Area;
  parent_id: number | null;
  topic_id: number | null;
  mastery_score: number | null;
  attempt_count: number;
  accuracy: number | null;
  average_time_ms: number | null;
  confidence: number | null;
  last_attempt: string | null;
  rollup: number | null;
  rollup_attempts: number;
  next_difficulty: Difficulty;
}

export interface Dashboard {
  areas: { area: Area; mastery: number | null; attempts: number }[];
  recent_attempts: { id: number; mode: "study" | "test"; title: string; score: number | null; max_score: number | null; submitted_at: string }[];
  study_streak: number;
  last_active_on: string | null;
  questions_answered: number;
  questions_answered_30d: number;
  overall_accuracy: number | null;
  weak_topics: string[];
  topics_completed: number;
}

export interface TestSection { name: string; time_limit_seconds: number | null }

export interface TestSummary {
  id: number;
  title: string;
  description: string;
  company: { id: number; name: string } | null;
  duration_seconds: number;
  sections: TestSection[];
  negative_marking: boolean;
  randomize: boolean;
  is_published: boolean;
  question_count: number;
  total_marks: number;
  created_at: string;
  active_attempt_id?: number | null;
  items?: AttemptItem[];
}

export interface AttemptItem {
  tq_id: number;
  section: string;
  marks: number;
  negative_marks: number;
  question: Question;
}

export interface SavedAnswer { answer: Answer | null; time_ms: number; flagged: boolean }

export interface AttemptView {
  id: number;
  status: "in_progress" | "submitted";
  test: TestSummary;
  started_at: string;
  server_now: string;
  deadline: string;
  sections: { name: string; deadline: string }[];
  items: AttemptItem[];
  answers: Record<string, SavedAnswer>;
  score: number | null;
  max_score: number | null;
  auto_submitted: boolean;
}

export interface AttemptListItem {
  id: number;
  mode: "study" | "test";
  status: string;
  title: string | null;
  test_id: number | null;
  score: number | null;
  max_score: number | null;
  started_at: string;
  submitted_at: string | null;
}

export interface AnalysisItem {
  tq_id: number;
  section: string;
  question_id: number;
  title: string;
  type: QuestionType;
  difficulty: Difficulty;
  topic: string | null;
  status: "correct" | "incorrect" | "unanswered" | "pending";
  judged_by: string | null;
  feedback: string;
  marks: number;
  awarded: number;
  time_ms: number;
  flagged: boolean;
  response: Answer | null;
  question: Question;
  answer: Record<string, unknown>;
  explanation: string;
}

export interface Breakdown { name: string; awarded: number; max: number; correct: number; attempted: number; time_ms: number }

export interface Analysis {
  attempt_id: number;
  test: TestSummary;
  status: string;
  auto_submitted: boolean;
  score: number;
  max_score: number;
  started_at: string;
  submitted_at: string;
  counts: { correct: number; incorrect: number; unanswered: number; pending: number };
  accuracy: number | null;
  total_time_ms: number;
  sections: Breakdown[];
  topics: Breakdown[];
  items: AnalysisItem[];
}

/* ---------------- Phase 3 ---------------- */

export interface ReadinessComponent {
  key: "dsa" | "csf" | "coding" | "aptitude" | "interview" | "consistency";
  label: string;
  value: number;
  weight: number;
  contribution: number;
  available: boolean;
  detail: string;
}

export interface ReadinessReport {
  company: { id: number; name: string; slug: string; pattern_disclaimer: string } | null;
  overall: number;
  formula: string;
  custom_weights: boolean;
  components: ReadinessComponent[];
  weaknesses: { name: string; area: string; mastery: number | null; priority: number; reason: string }[];
  recommendation: { component: string; title: string; detail: string; action: "study" | "code"; topic_id?: number; question_id?: number };
  history: { at: string; overall: number }[];
}

export interface CompanyReadiness { company_id: number; name: string; slug: string; overall: number; custom_weights?: boolean }

export interface Analytics {
  accuracy_over_time: { date: string; answered: number; correct: number; accuracy: number | null }[];
  topic_mastery: { topic: string; area: string; mastery: number; attempts: number }[];
  difficulty_distribution: { difficulty: Difficulty; attempted: number; correct: number }[];
  time_per_question: { submission_id: number; title: string; difficulty: Difficulty; type: QuestionType; time_ms: number; expected_ms: number; correct: boolean; at: string }[];
  company_readiness: (CompanyReadiness & Record<string, number | string>)[];
  weakest_topics: { topic: string; area: string; topic_id: number; mastery: number; accuracy: number; attempts: number; confidence: number | null; last_attempt: string | null }[];
  confidence_vs_accuracy: { topic: string; confidence: number; accuracy: number }[];
  total_scored: number;
}

/* ---------------- Phase 4 ---------------- */

export interface Citation { id: number; ref: string; title: string; topic: string | null; company: string | null; source_uri: string; score: number; snippet: string }

export interface AIEnvelope<T = Record<string, unknown>> {
  mode: string;
  data: T;
  citations: Citation[];
  grounded: boolean;
  checks: { input_flags: string[]; citations_dropped: string[]; grounded: boolean; safety: string; notes: string[]; hint_leak?: string };
  model: string | null;
  mock: boolean;
  cached: boolean;
}

export interface ReviewQuestion extends Question {
  review: {
    status: "pending_checks" | "ready_for_review" | "auto_rejected" | "approved" | "rejected";
    checks: Record<string, string>;
    citations: { id: number; title: string }[];
    generated_by: string;
    mock: boolean;
    note?: string;
  };
}

export interface CodeReview {
  summary: string; time_complexity: string; space_complexity: string; quality: string[]; edge_cases: string[];
  potential_defects: string[]; alternative_approach: string; verdict_at_review: string; removed_contradictions: string[];
  model: string; mock: boolean;
}

export interface ResumeView {
  id: number; filename: string; status: "pending" | "parsed" | "failed"; created_at: string;
  parsed: {
    skills?: string[]; projects?: { name: string; description: string; technologies: string[] }[];
    experience?: { role: string; organization: string; duration: string; highlights: string[] }[];
    education?: { degree: string; institution: string; year: string }[]; achievements?: string[]; error?: string; _mock?: boolean;
  };
}

export interface JDView {
  id: number; title: string; company_name: string; raw_text: string; status: "pending" | "parsed" | "failed"; created_at: string;
  parsed: { required_skills?: string[]; technologies?: string[]; responsibilities?: string[]; nice_to_have?: string[]; error?: string };
}

export interface GapReport {
  resume_id: number; jd_id: number; jd_title: string; job_readiness: number; matched: string[];
  missing: { skill: string; weight: number; action: "study" | "project"; topic_id?: number; topic?: string; suggestion: string }[];
  resume_skills: string[]; requirements: { skill: string; weight: number }[]; method: string;
}
