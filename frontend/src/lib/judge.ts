import { api } from "./api";

export type CodeLang = "python" | "cpp" | "java" | "javascript" | "sql";

export const LANG_LABEL: Record<CodeLang, string> = {
  python: "Python 3.13", cpp: "C++ (GCC 14)", java: "Java 13", javascript: "JavaScript (Node 22)", sql: "SQL (SQLite)",
};

export const STARTER: Record<CodeLang, string> = {
  python: "import sys\n\n\ndef main():\n    data = sys.stdin.read().split()\n    # your code here\n\n\nmain()\n",
  cpp: "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    // your code here\n    return 0;\n}\n",
  java: "import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n        // your code here\n    }\n}\n",
  javascript: "const data = require(\"fs\").readFileSync(0, \"utf8\").trim().split(/\\s+/);\n// your code here\n",
  sql: "-- write your query\nSELECT\n",
};

export interface CaseView {
  verdict: string;
  label: string;
  time_s: number | null;
  memory_kb: number | null;
  visible: boolean;
  stdin?: string;
  expected?: string | null;
  stdout?: string | null;
  stderr?: string | null;
}

export interface SubmissionView {
  id: number;
  question_id: number;
  mode: "run" | "submit" | "test";
  language: CodeLang;
  code: string;
  time_taken_ms: number | null;
  created_at: string;
  verdict: {
    status: string;
    label: string;
    is_correct: boolean;
    done: boolean;
    judged_by: string;
    details: {
      passed?: number; total?: number; cases?: CaseView[]; first_failed_case?: number | null;
      max_time_s?: number | null; max_memory_kb?: number | null; compile_output?: string | null; error?: string;
    };
  } | null;
}

export const VERDICT_TONE: Record<string, "ok" | "danger" | "warn" | "info" | "neutral"> = {
  accepted: "ok", wrong_answer: "danger", time_limit_exceeded: "warn", compilation_error: "danger",
  runtime_error: "danger", internal_error: "neutral", queued: "info", running: "info",
};

/** Submit and poll until Judge0's verdict is in. */
export async function judge(body: { question_id: number; language: CodeLang; code: string; mode: "run" | "submit"; stdin?: string; time_taken_ms?: number },
  onUpdate: (s: SubmissionView) => void, signal?: { cancelled: boolean }): Promise<SubmissionView> {
  let s = await api<SubmissionView>("/submissions", { method: "POST", json: body });
  onUpdate(s);
  let delay = 800;
  while (!s.verdict?.done) {
    await new Promise((r) => setTimeout(r, delay));
    if (signal?.cancelled) return s;
    s = await api<SubmissionView>(`/submissions/${s.id}`);
    onUpdate(s);
    delay = Math.min(delay * 1.3, 2500);
  }
  return s;
}
