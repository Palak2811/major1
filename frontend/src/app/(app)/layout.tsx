import { AppShell } from "@/components/AppShell";
import { RequireAuth } from "@/components/Guard";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireAuth>
      <AppShell>{children}</AppShell>
    </RequireAuth>
  );
}
