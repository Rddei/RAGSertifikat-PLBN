"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import { clearToken, getToken, setToken } from "./token";

// 1. TAMBAHKAN TIPE DATA USER
export interface UserPayload {
  username: string;
  role: string;
}

interface AuthState {
  isAuthenticated: boolean;
  ready: boolean;
  user: UserPayload | null; // 2. TAMBAHKAN STATE USER
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isAuthenticated, setAuthenticated] = useState(false);
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState<UserPayload | null>(null);

  useEffect(() => {
    const token = getToken();
    if (token) {
      setAuthenticated(true);
      // Baca data user dari localStorage jika sudah login sebelumnya
      const storedUser = localStorage.getItem("compliance_user");
      if (storedUser) {
        setUser(JSON.parse(storedUser));
      }
    }
    setReady(true);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    // 3. TERIMA DATA USER DARI BACKEND
    const res = await api.login(username, password);
    setToken(res.access_token);
    
    // Simpan objek user ke state dan localStorage
    if (res.user) {
      setUser(res.user);
      localStorage.setItem("compliance_user", JSON.stringify(res.user));
    }
    
    setAuthenticated(true);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    localStorage.removeItem("compliance_user"); // Hapus data saat logout
    setUser(null);
    setAuthenticated(false);
  }, []);

  const value: AuthState = { isAuthenticated, ready, user, login, logout };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth harus dipakai di dalam AuthProvider");
  return ctx;
}