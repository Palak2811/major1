import { RequireScope } from "@/components/Guard";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <RequireScope scope="admin:panel">{children}</RequireScope>;
}
