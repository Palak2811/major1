"use client";

import { useDeferredValue, useState } from "react";
import { QuestionFilters, useFilterString } from "@/components/QuestionFilters";
import { QuestionTable } from "@/components/QuestionTable";
import { Card, PageHeader } from "@/components/ui";

export default function QuestionsPage() {
  const [filters, setFilters] = useState<Record<string, string>>({});
  const filter = useFilterString(useDeferredValue(filters));
  return (
    <div>
      <PageHeader title="Question bank" description="Every published question, tagged by topic and company." />
      <Card>
        <QuestionFilters value={filters} onChange={setFilters} />
        <QuestionTable key={filter} filter={filter} />
      </Card>
    </div>
  );
}
