"use client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { api, User } from "@/lib/api";

type AuthContextValue = { user: User | null; loading: boolean; login: (email: string, password: string, role?: "GUARDIAN" | "DEPENDENT") => Promise<void>; register: (data: { email: string; password: string; display_name: string; role: "GUARDIAN" | "DEPENDENT"; mode: "OLDER_ADULT" | "MEMORY_SUPPORT" }) => Promise<void>; logout: () => Promise<void>; passwordChanged: () => void; refresh: () => Promise<void> };
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null); const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    const token = sessionStorage.getItem("memorycare_token");
    if (!token) { setUser(null); setLoading(false); return; }
    try { setUser(await api<User>("/auth/me")); } catch { sessionStorage.removeItem("memorycare_token"); setUser(null); } finally { setLoading(false); }
  }, []);
  useEffect(() => { const timer=window.setTimeout(()=>void refresh(),0); return ()=>window.clearTimeout(timer); }, [refresh]);
  useEffect(() => { const onExpired=()=>{setUser(null);router.replace("/login?expired=1");};window.addEventListener("memorycare:session-expired",onExpired);return()=>window.removeEventListener("memorycare:session-expired",onExpired); }, [router]);
  const login = useCallback(async (email: string, password: string, role?: "GUARDIAN" | "DEPENDENT") => {
    const data = await api<{ access_token: string; user: User }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password, ...(role ? { role } : {}) }) });
    if (role && !data.user.roles.includes(role)) throw new Error("This account does not match the selected sign-in type.");
    sessionStorage.setItem("memorycare_token", data.access_token); setUser(data.user);
  }, []);
  const register = useCallback(async (payload: { email: string; password: string; display_name: string; role: "GUARDIAN" | "DEPENDENT"; mode: "OLDER_ADULT" | "MEMORY_SUPPORT" }) => {
    const data = await api<{ access_token: string; user: User }>("/auth/register", { method: "POST", body: JSON.stringify(payload) });
    sessionStorage.setItem("memorycare_token", data.access_token); setUser(data.user);
  }, []);
  const logout = useCallback(async () => { try { await api("/auth/logout", { method: "POST" }); } finally { sessionStorage.removeItem("memorycare_token"); setUser(null); router.replace("/"); } }, [router]);
  const passwordChanged = useCallback(() => { sessionStorage.removeItem("memorycare_token"); setUser(null); router.replace("/login?passwordChanged=1"); }, [router]);
  const value = useMemo(() => ({ user, loading, login, register, logout, passwordChanged, refresh }), [user, loading, login, register, logout, passwordChanged, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() { const value = useContext(AuthContext); if (!value) throw new Error("useAuth must be used inside AuthProvider"); return value; }
