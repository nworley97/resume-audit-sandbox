import { redirect } from "next/navigation";
import { env } from "@/lib/env";

export default function Home() {
  if (env.defaultTenant) {
    redirect(`/${env.defaultTenant}/recruiter/analytics`);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6 text-center text-sm text-muted-foreground">
      Set NEXT_PUBLIC_ANALYTICS_TENANT to redirect to a tenant dashboard, e.g. <code className="mx-1 rounded bg-muted px-1">acme</code>.
    </div>
  );
}
