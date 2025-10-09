import { useEffect, useMemo, useState, type ComponentType, type ReactNode, type SVGProps } from "react";
import { Link, useLocation } from "react-router-dom";
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

function tenantInitials(label: string) {
  const letters = label
    .split(" ")
    .filter(Boolean)
    .map((part) => part[0]?.toUpperCase() ?? "");
  return letters.join("").slice(0, 2) || "AL";
}

interface TenantMetadata {
  slug: string;
  display_name: string;
  logo_url?: string | null;
}

export function DashboardChrome({
  tenant,
  children,
}: {
  tenant: string;
  children: ReactNode;
}) {
  const location = useLocation();
  const pathname = location.pathname;
  const [tenantMeta, setTenantMeta] = useState<TenantMetadata | null>(null);
  const [metaLoaded, setMetaLoaded] = useState(false);
  const [logoLoaded, setLogoLoaded] = useState(false);
  const [logoErrored, setLogoErrored] = useState(false);
  const [userInitials, setUserInitials] = useState("JD");
  const [userLoaded, setUserLoaded] = useState(false);
  const tenantLabel = useMemo(() => {
    if (tenantMeta?.display_name) {
      return tenantMeta.display_name;
    }
    const cleaned = tenant.replace(/[-_]+/g, " ").trim();
    if (!cleaned) return "Altera";
    return cleaned.replace(/\b\w/g, (char) => char.toUpperCase());
  }, [tenant, tenantMeta?.display_name]);
  const brandInitials = tenantInitials(tenantLabel);

  useEffect(() => {
    let cancelled = false;
    setTenantMeta(null);
    setMetaLoaded(false);
    setLogoLoaded(false);
    setLogoErrored(false);
    async function fetchTenantMeta() {
      try {
        const res = await fetch(`/api/tenants/${encodeURIComponent(tenant)}/metadata`, {
          credentials: "include",
          headers: {
            "Accept": "application/json",
          },
        });
        if (!res.ok) return;
        const data = (await res.json()) as TenantMetadata;
        if (!cancelled) {
          setTenantMeta(data);
        }
      } catch (error) {
        // Silently ignore metadata fetch errors to avoid blocking the UI.
      } finally {
        if (!cancelled) {
          setMetaLoaded(true);
        }
      }
    }

    fetchTenantMeta();
    return () => {
      cancelled = true;
    };
  }, [tenant]);

  useEffect(() => {
    setLogoLoaded(false);
    setLogoErrored(false);
  }, [tenantMeta?.logo_url]);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage?.getItem("analytics-user-initials");
    if (stored) {
      setUserInitials(stored.slice(0, 2).toUpperCase());
      setUserLoaded(true);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function fetchUserIdentity() {
      try {
        const res = await fetch("/api/session/me", {
          credentials: "include",
          headers: {
            Accept: "application/json",
          },
        });
        if (!res.ok) return;
        const data = (await res.json()) as { initials?: string; username?: string };
        if (!cancelled) {
          const nextInitials = (data.initials || data.username || "JD").slice(0, 2).toUpperCase();
          setUserInitials(nextInitials);
          if (typeof window !== "undefined") {
            try {
              window.localStorage?.setItem("analytics-user-initials", nextInitials);
            } catch (storageError) {
              // Ignore storage errors (e.g., privacy mode).
            }
          }
        }
      } catch (error) {
        // Ignore errors; fallback initials remain.
      } finally {
        if (!cancelled) {
          setUserLoaded(true);
        }
      }
    }

    fetchUserIdentity();
    return () => {
      cancelled = true;
    };
  }, []);
  return (
    <div className="min-h-screen flex bg-white text-slate-900">
      <aside className="w-56 bg-white border-r border-gray-200 relative">
        <div className="flex items-center gap-3 px-4 py-4">
          <div className="relative w-8 h-8 rounded-full overflow-hidden flex items-center justify-center bg-gray-900 text-white text-xs">
            {!metaLoaded ? (
              <div className="h-full w-full animate-pulse bg-gray-200" aria-hidden />
            ) : tenantMeta?.logo_url && !logoErrored ? (
              <>
                {!logoLoaded ? (
                  <div className="absolute inset-0 animate-pulse bg-gray-200" aria-hidden />
                ) : null}
                <img
                  src={tenantMeta.logo_url}
                  alt={`${tenantLabel} logo`}
                  className={`h-full w-full object-cover transition-opacity duration-200 ${
                    logoLoaded ? "opacity-100" : "opacity-0"
                  }`}
                  onLoad={() => setLogoLoaded(true)}
                  onError={() => {
                    setLogoErrored(true);
                    setLogoLoaded(false);
                  }}
                />
              </>
            ) : (
              <span>{brandInitials}</span>
            )}
          </div>
          <div className="min-w-0 flex items-center">
            {!metaLoaded ? (
              <div className="h-4 w-24 rounded bg-gray-200 animate-pulse" aria-hidden />
            ) : (
              <span className="text-sm font-medium text-slate-900 leading-tight truncate max-w-[9rem]">
                {tenantLabel}
              </span>
            )}
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
            
            const className = `${index > 0 ? "mt-1" : ""} flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition ${
              isActive ? "bg-primary/10 text-primary" : "text-slate-900 hover:bg-gray-50"
            }`;

            if (label === "Analytics") {
              return (
                <Link key={label} to={url} className={className}>
                  <Icon className="w-4 h-4" aria-hidden />
                  <span>{label}</span>
                </Link>
              );
            }

            return (
              <a key={label} href={url} className={className}>
                <Icon className="w-4 h-4" aria-hidden />
                <span>{label}</span>
              </a>
            );
          })}
        </nav>

        <div className="absolute left-4 bottom-4 flex items-center gap-2 text-xs text-slate-500">
          <img
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
            <a
              href="/logout"
              className="inline-flex items-center rounded-lg border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-50"
            >
              Sign out
            </a>
            <div className="w-8 h-8 rounded-full bg-gray-900 text-white text-xs flex items-center justify-center">
              {userLoaded ? (
                <span>{userInitials}</span>
              ) : (
                <div className="h-4 w-4 animate-pulse bg-gray-200 rounded" aria-hidden />
              )}
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
