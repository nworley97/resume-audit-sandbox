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
  // Check if viewport is tablet or smaller
  const isTabletOrSmaller = () => {
    if (typeof window === "undefined") return false;
    return window.innerWidth < 1024;
  };

  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    try {
      const stored = window.localStorage?.getItem("app-sidebar-collapsed");
      
      // Smart responsive behavior on initial load
      if (isTabletOrSmaller()) {
        // Auto-collapse on tablet/mobile
        return true;
      } else {
        // On desktop, respect user preference or default to expanded
        const hasStoredPreference = stored !== null;
        if (!hasStoredPreference) {
          // First visit on desktop - default to expanded
          return false;
        }
        return stored === "1";
      }
    } catch {
      return isTabletOrSmaller();
    }
  });
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
      } catch {
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
            } catch {
              // Ignore storage errors (e.g., privacy mode).
            }
          }
        }
      } catch {
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

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.body.classList.toggle("sidebar-collapsed", sidebarCollapsed);
    try {
      window.localStorage?.setItem("app-sidebar-collapsed", sidebarCollapsed ? "1" : "0");
    } catch {
      // ignore storage issues
    }
  }, [sidebarCollapsed]);

  // Handle window resize with smart responsive behavior
  useEffect(() => {
    if (typeof window === "undefined") return;

    let resizeTimer: NodeJS.Timeout;
    let isResizing = false;
    
    const handleResize = () => {
      if (isResizing) return;
      isResizing = true;
      
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        const isNowTabletOrSmaller = isTabletOrSmaller();
        
        if (isNowTabletOrSmaller) {
          // Auto-collapse on tablet/mobile
          setSidebarCollapsed(true);
        } else if (sidebarCollapsed) {
          // Auto-expand when returning to desktop from mobile
          setSidebarCollapsed(false);
          // Save the expanded state for desktop
          try {
            localStorage.setItem("app-sidebar-collapsed", "0");
          } catch {
            // ignore storage errors
          }
        }
        
        isResizing = false;
      }, 200);
    };

    window.addEventListener("resize", handleResize);
    return () => {
      clearTimeout(resizeTimer);
      window.removeEventListener("resize", handleResize);
    };
  }, [sidebarCollapsed]);

  const toggleSidebar = () => {
    setSidebarCollapsed((prev) => !prev);
  };

  const ExpandedIcon = (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <rect x="6" y="8" width="5" height="8" rx="1" />
    </svg>
  );

  const CollapsedIcon = (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="h-4 w-4"
    >
      <rect x="3" y="5" width="18" height="14" rx="2" />
      <rect x="13" y="8" width="5" height="8" rx="1" />
    </svg>
  );

  return (
    <div className="min-h-screen flex bg-white text-slate-900">
      <aside
        className={`bg-white border-r border-gray-200 relative transition-all duration-300 ease-out overflow-hidden ${
          sidebarCollapsed ? "w-[4.5rem]" : "w-56"
        }`}
      >
        <div
          className={`flex items-center gap-2 py-4 px-4 transition-all duration-200 ${
            sidebarCollapsed ? "justify-center" : ""
          }`}
        >
          <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center">
            <div className="relative h-10 w-10 rounded-full overflow-hidden flex items-center justify-center bg-gray-900 text-white text-xs">
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
          </div>
          {!sidebarCollapsed && (
            <div className="min-w-0 flex items-center">
              {!metaLoaded ? (
                <div className="h-4 w-24 rounded bg-gray-200 animate-pulse" aria-hidden />
              ) : (
                <span className="text-sm font-medium text-slate-900 leading-tight truncate max-w-[9rem]">
                  {tenantLabel}
                </span>
              )}
            </div>
          )}
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
            
            const className = [
              index > 0 ? "mt-1" : "",
              "flex items-center rounded-lg text-sm transition py-2",
              sidebarCollapsed ? "justify-center px-2" : "gap-2 px-3",
              isActive ? "bg-primary/10 text-primary" : "text-slate-900 hover:bg-gray-50",
            ]
              .filter(Boolean)
              .join(" ");

            if (label === "Analytics") {
              return (
                <Link key={label} to={url} className={className} aria-label={label}>
                  <Icon className="w-4 h-4" aria-hidden />
                  {!sidebarCollapsed && <span>{label}</span>}
                </Link>
              );
            }

            return (
              <a key={label} href={url} className={className} aria-label={label}>
                <Icon className="w-4 h-4" aria-hidden />
                {!sidebarCollapsed && <span>{label}</span>}
              </a>
            );
          })}
        </nav>

        <div
          className={`absolute bottom-4 flex items-center text-xs text-slate-500 leading-4 ${
            sidebarCollapsed ? "left-1/2 -translate-x-1/2 flex-col gap-1 text-center" : "left-2 gap-1.5 justify-start px-3"
          }`}
        >
          <img
            src="/favicon-32x32.png"
            alt="Altera mark"
            width={16}
            height={16}
            className="rounded"
          />
          {!sidebarCollapsed && (
            <a 
              href="https://alterasf.com/" 
              target="_blank" 
              rel="noopener noreferrer"
              className="hover:text-slate-700 hover:underline cursor-pointer transition-colors duration-200"
            >
              Powered by AlteraSF
            </a>
          )}
        </div>
      </aside>

      <div className="flex-1 flex flex-col min-w-0">
        <header className="w-full bg-white border-b border-gray-200">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={toggleSidebar}
                className="sidebar-toggle inline-flex items-center justify-center bg-white text-slate-700 px-3 py-2 rounded-lg hover:bg-[#EAEAEA] transition-colors focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-primary/60"
                aria-label="Toggle navigation"
                aria-pressed={sidebarCollapsed ? "true" : "false"}
              >
                {sidebarCollapsed ? CollapsedIcon : ExpandedIcon}
              </button>
            </div>
            <div className="flex items-center gap-3">
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
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
