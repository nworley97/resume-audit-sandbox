"use client";

import type { ComponentType, ReactNode, SVGProps } from "react";
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { LayoutGrid, Users2, BarChart2 } from "lucide-react";

type NavItem = {
  label: string;
  href: (tenant: string) => string;
  icon: ComponentType<SVGProps<SVGSVGElement>>;
};

const NAV_ITEMS: NavItem[] = [
  {
    label: "Job Posting",
    href: (tenant) => `/${tenant}/recruiter`,
    icon: LayoutGrid,
  },
  {
    label: "Candidates",
    href: (tenant) => `/${tenant}/recruiter/candidates`,
    icon: Users2,
  },
  {
    label: "Analytics",
    href: (tenant) => `/${tenant}/recruiter/analytics`,
    icon: BarChart2,
  },
];

function formatTenantLabel(rawTenant?: string) {
  const cleaned = (rawTenant ?? "Altera").replace(/[-_]+/g, " ").trim();
  if (!cleaned) return "Altera";
  return cleaned.replace(/\b\w/g, (char) => char.toUpperCase());
}

function tenantInitials(label: string) {
  const letters = label
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() ?? "");
  return letters.join("").slice(0, 2) || "AL";
}

export function DashboardChrome({
  tenant,
  children,
}: {
  tenant: string;
  children: ReactNode;
}) {
  const pathname = usePathname();
  const tenantLabel = formatTenantLabel(tenant);
  const brandInitials = tenantInitials(tenantLabel);

  return (
    <div className="min-h-screen flex bg-white text-slate-900">
      <aside className="w-56 bg-white border-r border-gray-200 relative">
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="w-8 h-8 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center">
            {brandInitials}
          </div>
          <div className="min-w-0 flex items-center">
            <span className="text-sm font-medium text-slate-900 leading-tight truncate max-w-[9rem]">
              {tenantLabel}
            </span>
          </div>
        </div>

        <nav className="px-2">
          {NAV_ITEMS.map(({ label, href, icon: Icon }, index) => {
            const url = href(tenant);
            // Special path matching logic to prevent conflicts
            let isActive = false;
            
            if (label === "Job Posting") {
              // Job Posting: exact path matching only (exclude sub-paths)
              isActive = pathname === url;
            } else {
              // Analytics, Candidates: exact path + sub-paths included
              isActive = pathname === url || pathname.startsWith(`${url}/`);
            }
            
            return (
              <Link
                key={label}
                href={url}
                className={`${index > 0 ? "mt-1" : ""} flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-slate-900 hover:bg-gray-50"
                }`}
              >
                <Icon className="w-4 h-4" aria-hidden />
                <span>{label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="absolute left-4 bottom-4 flex items-center gap-2 text-xs text-slate-500">
          <Image
            src="/favicon-32x32.png"
            alt="Altera mark"
            width={16}
            height={16}
            className="rounded"
          />
          Powered by AlteraSF
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="w-full bg-white border-b border-gray-200">
          <div className="flex items-center justify-end gap-3 px-4 py-3">
            <Link
              href="/logout"
              className="inline-flex items-center rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              Sign out
            </Link>
            <div className="w-8 h-8 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center">
              {brandInitials}
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
