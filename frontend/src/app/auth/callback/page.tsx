"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/lib/auth";

// The backend's OAuth callback has already set the refresh cookie; exchange it for an access token.
export default function OAuthCallback() {
  const { bootstrap } = useAuth();
  const router = useRouter();
  useEffect(() => {
    void bootstrap().then((ok) => router.replace(ok ? "/dashboard" : "/login?error=oauth_state"));
  }, [bootstrap, router]);
  return (
    <div className="grid h-screen place-items-center">
      <div className="flex items-center gap-2 text-sm text-muted"><Spinner /> Completing Google sign-in…</div>
    </div>
  );
}
