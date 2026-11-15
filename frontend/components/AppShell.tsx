"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { useAuth, type Role } from "@/lib/auth-context";
import { samsRequest } from "@/lib/api";

interface MenuItem {
  href: string;
  label: string;
  icon: string;
  /** Renders the pending-approval count next to the item. */
  badge?: "leave-inbox";
  /** Draws a thin separator above the item (settings grouped under a section). */
  dividerBefore?: boolean;
}

interface MenuSection {
  id: string;
  label: string;
  items: MenuItem[];
}

interface RoleMenu {
  top: MenuItem;
  sections: MenuSection[];
  /** Standalone links rendered after the sections (e.g. student profile). */
  extras?: MenuItem[];
}

const ADMIN_MENU: RoleMenu = {
  top: { href: "/admin/dashboard", label: "ภาพรวม", icon: "📊" },
  sections: [
    {
      id: "leaves",
      label: "ใบลา",
      items: [
        { href: "/admin/leaves", label: "คำร้องลานักศึกษา", icon: "📝" },
        {
          href: "/approvals",
          label: "คิวพิจารณา",
          icon: "🗳️",
          badge: "leave-inbox",
        },
        {
          href: "/admin/leave-roles",
          label: "ผู้รับผิดชอบ Workflow",
          icon: "🧩",
          dividerBefore: true,
        },
        {
          href: "/admin/leave-workflow",
          label: "ลำดับขั้นตอน Workflow",
          icon: "🛠️",
        },
      ],
    },
    {
      id: "attendance",
      label: "การเช็คชื่อ",
      items: [
        {
          href: "/admin/attendance-sessions",
          label: "คาบเรียนเช็คชื่อ",
          icon: "🟢",
        },
        {
          href: "/admin/attendance-records",
          label: "รายการเช็คชื่อ",
          icon: "✅",
        },
        {
          href: "/admin/reports",
          label: "รายงานการเข้าเรียน",
          icon: "📈",
        },
      ],
    },
    {
      id: "academics",
      label: "การเรียนการสอน",
      items: [
        {
          href: "/admin/course-offerings",
          label: "เปิดสอนรายวิชา",
          icon: "📚",
        },
        { href: "/admin/enrollments", label: "การลงทะเบียน", icon: "🗒️" },
        { href: "/admin/schedules", label: "ตารางเรียน", icon: "⏰" },
      ],
    },
    {
      id: "master-data",
      label: "ข้อมูลพื้นฐาน",
      items: [
        { href: "/admin/students", label: "นักศึกษา", icon: "🎓" },
        { href: "/admin/instructors", label: "อาจารย์", icon: "🧑‍🏫" },
        { href: "/admin/programs", label: "หลักสูตร", icon: "🏅" },
        { href: "/admin/class-groups", label: "กลุ่มเรียน", icon: "🏫" },
        { href: "/admin/academic-terms", label: "ภาคการศึกษา", icon: "📅" },
        { href: "/admin/courses", label: "รายวิชา", icon: "📘" },
      ],
    },
    {
      id: "system",
      label: "ระบบ",
      items: [
        { href: "/admin/users", label: "ผู้ใช้งาน", icon: "👥" },
        { href: "/admin/audit-logs", label: "บันทึกการใช้งาน", icon: "🧾" },
      ],
    },
  ],
};

const INSTRUCTOR_MENU: RoleMenu = {
  top: { href: "/instructor/dashboard", label: "ภาพรวม", icon: "📊" },
  sections: [
    {
      id: "my-teaching",
      label: "การสอนของฉัน",
      items: [
        { href: "/instructor/courses", label: "รายวิชาของฉัน", icon: "📘" },
        { href: "/instructor/schedule", label: "ตารางสอน", icon: "🗓️" },
      ],
    },
    {
      id: "manage-courses",
      label: "จัดการรายวิชา",
      items: [
        {
          href: "/instructor/course-offerings",
          label: "เปิดสอนรายวิชา",
          icon: "📚",
        },
        {
          href: "/instructor/enrollments",
          label: "การลงทะเบียน",
          icon: "🗒️",
        },
        { href: "/instructor/schedules", label: "ตารางเรียน", icon: "⏰" },
      ],
    },
    {
      id: "attendance",
      label: "การเช็คชื่อ",
      items: [
        { href: "/instructor/attendance", label: "เปิดเช็คชื่อ", icon: "🟢" },
        {
          href: "/instructor/reports",
          label: "รายงานการเข้าเรียน",
          icon: "📈",
        },
      ],
    },
    {
      id: "leaves",
      label: "ใบลา",
      items: [
        {
          href: "/instructor/leaves",
          label: "คำร้องลาในรายวิชา",
          icon: "📝",
        },
        {
          href: "/approvals",
          label: "คิวพิจารณา",
          icon: "🗳️",
          badge: "leave-inbox",
        },
      ],
    },
  ],
};

const STUDENT_MENU: RoleMenu = {
  top: { href: "/student/dashboard", label: "ภาพรวม", icon: "📊" },
  sections: [
    {
      id: "my-study",
      label: "การเรียนของฉัน",
      items: [
        { href: "/student/courses", label: "รายวิชาที่ลงทะเบียน", icon: "📘" },
        { href: "/student/schedule", label: "ตารางเรียน", icon: "⏰" },
      ],
    },
    {
      id: "attendance",
      label: "การเช็คชื่อ",
      items: [
        { href: "/student/scan", label: "สแกน QR Code", icon: "📷" },
        { href: "/student/history", label: "ประวัติการเช็คชื่อ", icon: "✅" },
      ],
    },
    {
      id: "leaves",
      label: "ใบลา",
      items: [{ href: "/student/leaves", label: "ใบลาของฉัน", icon: "📝" }],
    },
  ],
  extras: [{ href: "/student/profile", label: "โปรไฟล์", icon: "👤" }],
};

const MENU_BY_ROLE: Record<Role, RoleMenu> = {
  admin: ADMIN_MENU,
  instructor: INSTRUCTOR_MENU,
  student: STUDENT_MENU,
};

/** Exact match, or a descendant path — avoids `/admin/leaves` lighting up
 * `/admin/leave-roles` and `/admin/leave-workflow`. */
function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

function storageKey(role: Role): string {
  return `sams:menu-open:${role}`;
}

function readOpenSections(role: Role): Record<string, boolean> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(storageKey(role));
    if (!raw) return {};
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return {};
    const result: Record<string, boolean> = {};
    for (const [key, value] of Object.entries(parsed as Record<string, unknown>)) {
      if (typeof value === "boolean") result[key] = value;
    }
    return result;
  } catch {
    return {};
  }
}

function SidebarNav({
  role,
  inboxCount,
  onNavigate,
  onLogout,
}: {
  role: Role;
  inboxCount: number;
  onNavigate?: () => void;
  onLogout: () => void;
}) {
  const pathname = usePathname() ?? "";
  const menu = MENU_BY_ROLE[role];
  const [openSections, setOpenSections] = useState<Record<string, boolean>>(
    () => readOpenSections(role),
  );
  const [query, setQuery] = useState("");

  const activeSectionId = useMemo(() => {
    const match = menu.sections.find((section) =>
      section.items.some((item) => isActive(pathname, item.href)),
    );
    return match?.id ?? null;
  }, [menu.sections, pathname]);

  const searchable = useMemo(
    () => [
      { item: menu.top, sectionLabel: "เมนูหลัก", sectionId: "__top" },
      ...menu.sections.flatMap((section) =>
        section.items.map((item) => ({
          item,
          sectionLabel: section.label,
          sectionId: section.id,
        })),
      ),
      ...(menu.extras ?? []).map((item) => ({
        item,
        sectionLabel: "เมนูหลัก",
        sectionId: "__top",
      })),
    ],
    [menu],
  );

  const showSearch = searchable.length > 8;
  const normalizedQuery = query.trim().toLowerCase();

  const searchGroups = useMemo(() => {
    if (!normalizedQuery) return [];
    const groups: { id: string; label: string; items: MenuItem[] }[] = [];
    for (const entry of searchable) {
      if (!entry.item.label.toLowerCase().includes(normalizedQuery)) continue;
      const existing = groups.find((group) => group.id === entry.sectionId);
      if (existing) {
        existing.items.push(entry.item);
      } else {
        groups.push({
          id: entry.sectionId,
          label: entry.sectionLabel,
          items: [entry.item],
        });
      }
    }
    return groups;
  }, [normalizedQuery, searchable]);

  const toggleSection = (id: string) => {
    if (id === activeSectionId) return; // keep the current page visible
    setOpenSections((prev) => {
      const next = { ...prev, [id]: !(prev[id] ?? false) };
      if (typeof window !== "undefined") {
        try {
          window.localStorage.setItem(storageKey(role), JSON.stringify(next));
        } catch {
          // private mode / quota — collapse state just won't persist
        }
      }
      return next;
    });
  };

  const renderLink = (item: MenuItem, keyPrefix: string) => {
    const active = isActive(pathname, item.href);
    const badgeCount = item.badge === "leave-inbox" ? inboxCount : 0;
    return (
      <Link
        key={`${keyPrefix}${item.href}`}
        href={item.href}
        onClick={() => {
          setQuery("");
          onNavigate?.();
        }}
        aria-current={active ? "page" : undefined}
        className={`relative flex items-center gap-2 rounded-lg py-2 pl-3 pr-2 text-sm transition ${
          active
            ? "bg-blue-50 font-semibold text-blue-800"
            : "text-slate-700 hover:bg-blue-50 hover:text-blue-800"
        }`}
      >
        {active && (
          <span
            aria-hidden
            className="absolute inset-y-1 left-0 w-1 rounded-full bg-blue-600"
          />
        )}
        <span aria-hidden>{item.icon}</span>
        <span className="min-w-0 flex-1 truncate">{item.label}</span>
        {badgeCount > 0 && (
          <span
            aria-label={`งานค้าง ${badgeCount} รายการ`}
            className="shrink-0 rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-amber-700"
          >
            {badgeCount > 99 ? "99+" : badgeCount}
          </span>
        )}
      </Link>
    );
  };

  return (
    <nav className="flex min-h-full flex-col p-3">
      <div className="px-3 pb-3 pt-2">
        <div className="text-lg font-bold text-blue-900">SAMS</div>
        <div className="text-xs text-slate-500">
          Student Attendance Mgmt. System
        </div>
      </div>

      {showSearch && (
        <div className="px-1 pb-2">
          <label htmlFor={`menu-search-${role}`} className="sr-only">
            ค้นหาเมนู
          </label>
          <input
            id={`menu-search-${role}`}
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="ค้นหาเมนู…"
            className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 text-sm text-slate-700 placeholder:text-slate-400 focus:border-blue-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-100"
          />
        </div>
      )}

      {normalizedQuery ? (
        <div className="flex flex-col gap-3 pb-2">
          {searchGroups.length === 0 ? (
            <p className="px-3 py-2 text-sm text-slate-500">
              ไม่พบเมนูที่ค้นหา
            </p>
          ) : (
            searchGroups.map((group) => (
              <div key={group.id} className="flex flex-col gap-0.5">
                <div className="px-3 text-[11px] font-medium text-slate-400">
                  {group.label}
                </div>
                {group.items.map((item) =>
                  renderLink(item, `search-${group.id}-`),
                )}
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="flex flex-col gap-0.5">
          {renderLink(menu.top, "top-")}

          {menu.sections.map((section) => {
            const isCurrent = section.id === activeSectionId;
            const open = isCurrent || openSections[section.id] === true;
            const sectionBadge = section.items.reduce(
              (total, item) =>
                total + (item.badge === "leave-inbox" ? inboxCount : 0),
              0,
            );
            const headerContent = (
              <>
                <span
                  aria-hidden
                  className={`inline-block text-[10px] transition-transform ${
                    open ? "rotate-90" : ""
                  }`}
                >
                  ▶
                </span>
                <span className="flex-1">{section.label}</span>
                {sectionBadge > 0 && (
                  <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold leading-none text-amber-700">
                    {sectionBadge > 99 ? "99+" : sectionBadge}
                  </span>
                )}
              </>
            );
            const headerClass =
              "flex w-full items-center gap-2 rounded-lg px-3 py-1.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-500";
            return (
              <div key={section.id} className="mt-1">
                {/* The section holding the current page always stays open. */}
                {isCurrent ? (
                  <div className={headerClass}>{headerContent}</div>
                ) : (
                  <button
                    type="button"
                    onClick={() => toggleSection(section.id)}
                    aria-expanded={open}
                    className={`${headerClass} hover:bg-slate-100`}
                  >
                    {headerContent}
                  </button>
                )}

                {open && (
                  <div className="mt-0.5 flex flex-col gap-0.5 pl-2">
                    {section.items.map((item) => (
                      <div key={`${section.id}${item.href}`}>
                        {item.dividerBefore && (
                          <div
                            aria-hidden
                            className="my-1 border-t border-slate-100"
                          />
                        )}
                        {renderLink(item, `${section.id}-`)}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}

          {(menu.extras ?? []).map((item) => (
            <div key={`extra${item.href}`} className="mt-1">
              {renderLink(item, "extra-")}
            </div>
          ))}
        </div>
      )}

      <button
        type="button"
        onClick={onLogout}
        className="mt-auto flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
      >
        🚪 ออกจากระบบ
      </button>
    </nav>
  );
}

export default function AppShell({
  children,
  title,
}: {
  children: React.ReactNode;
  title: string;
}) {
  const { user, logout, loading } = useAuth();
  const pathname = usePathname() ?? "";
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [inboxCount, setInboxCount] = useState(0);
  const role = user?.role ?? null;
  const showBadge = role === "admin" || role === "instructor";

  useEffect(() => {
    if (!showBadge) return;
    let cancelled = false;
    void (async () => {
      try {
        const { envelope } = await samsRequest<unknown>({
          url: "/leave-approvals/",
          method: "GET",
          params: { page_size: 1 },
        });
        if (!cancelled) setInboxCount(envelope.pagination?.count ?? 0);
      } catch {
        // Badge is best-effort — never block the menu on a count failure.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [showBadge, pathname]);

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <div className="animate-pulse text-slate-500">กำลังโหลดระบบ…</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 overflow-y-auto border-r border-slate-200 bg-white lg:block">
        {user && (
          <SidebarNav
            role={user.role}
            inboxCount={inboxCount}
            onLogout={() => void logout()}
          />
        )}
      </aside>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button
            type="button"
            aria-label="ปิดเมนู"
            className="absolute inset-0 bg-slate-900/40"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute inset-y-0 left-0 w-72 overflow-y-auto bg-white shadow-lg">
            {user && (
              <SidebarNav
                role={user.role}
                inboxCount={inboxCount}
                onNavigate={() => setDrawerOpen(false)}
                onLogout={() => void logout()}
              />
            )}
          </aside>
        </div>
      )}

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="เปิดเมนู"
              className="rounded-lg border border-slate-200 px-3 py-1.5 text-slate-600 lg:hidden"
              onClick={() => setDrawerOpen(true)}
            >
              ☰
            </button>
            <h1 className="text-base font-semibold text-slate-900 md:text-lg">{title}</h1>
          </div>
          {user && (
            <div className="flex items-center gap-3">
              <span className="hidden text-sm text-slate-500 md:inline">
                {user.profile?.first_name ?? user.username} ({user.role_th})
              </span>
              <button
                type="button"
                onClick={() => void logout()}
                className="rounded-lg bg-blue-700 px-3 py-1.5 text-sm text-white hover:bg-blue-800"
              >
                ออกจากระบบ
              </button>
            </div>
          )}
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6">{children}</main>
        <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-400">
          SAMS v1.0.0 — Student Attendance Management System
        </footer>
      </div>
    </div>
  );
}
