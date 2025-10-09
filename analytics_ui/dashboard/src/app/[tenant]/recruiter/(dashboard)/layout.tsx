import type { Metadata } from "next";
import { DashboardChrome } from "@/components/layout/dashboard-chrome";

export const metadata: Metadata = {
  title: "Analytics Dashboard • Altera",
};

export const dynamic = "force-dynamic";

export default async function DashboardLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ tenant: string }>;
}) {
  const { tenant } = await params;

  return <DashboardChrome tenant={tenant}>{children}</DashboardChrome>;
}
