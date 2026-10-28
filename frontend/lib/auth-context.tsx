"use client";
/**
 * AuthProvider (React context) — manages the SAMS session.
 * Access token: memory only. Refresh token: HttpOnly cookie from Django.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { useRouter } from "next/navigation";
import { api, refreshSession, setAccessToken, setSessionExpiredHandler, samsRequest } from "@/lib/api";

export type Role = "admin" | "instructor" | "student";

export interface SamsUser {
  id: string;
  username: string;
  role: Role;
  role_th?: string;
  profile?: {
    student_code?: string;
    employee_code?: string;
    first_name?: string;
    last_name?: string;
  } | null;
}

interface AuthContextValue {
  user: SamsUser | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<SamsUser>;
  logout: () => Promise<void>;
  refreshHydration: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const ROLE_HOME: Record<Role, string> = {
  admin: "/admin/dashboard",
  instructor: "/instructor/dashboard",
  student: "/student/dashboard",
};

export function roleHome(role: Role): string {
  return ROLE_HOME[role];
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SamsUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const refreshHydration = useCallback(async () => {
    setLoading(true);
    // Route through api.ts single-flight refreshSession to avoid a concurrent
    // double rotation (refresh cookie rotation + blacklist breaks under races,
    // which used to leave a blacklisted cookie and force-logout on page load).
    const ok = await refreshSession();
    try {
      if (ok) {
        const me = await samsRequest<SamsUser>({ url: "/auth/me/" });
        setUser(me.data);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      router.replace("/login");
    });
    void (async () => {
      await Promise.resolve(); // yield ก่อน setState (react-hooks/set-state-in-effect)
      await refreshHydration();
    })();
  }, [refreshHydration, router]);

  const login = useCallback(
    async (username: string, password: string): Promise<SamsUser> => {
      const { data } = await samsRequest<{ access: string; user: SamsUser }>({
        url: "/auth/login/",
        method: "POST",
        data: { username, password },
      });
      // Backend returns { access, user: {...} } — the user object is nested.
      setAccessToken(data.access);
      setUser(data.user);
      return data.user;
    },
    [],
  );

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout/", {});
    } catch {
      // logout should never block the UI
    }
    setAccessToken(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, login, logout, refreshHydration }),
    [user, loading, login, logout, refreshHydration],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth ต้องถูกใช้ภายใน AuthProvider เท่านั้น");
  }
  return context;
}

export function useRequireRole(allowed: Role[]): SamsUser {
  const { user, loading } = useAuth();
  const router = useRouter();
  useEffect(() => {
    if (loading) return;
    if (!user) {
      router.replace("/login");
    } else if (!allowed.includes(user.role)) {
      router.replace(roleHome(user.role));
    }
  }, [user, loading, allowed, router]);
  return user!;
}
