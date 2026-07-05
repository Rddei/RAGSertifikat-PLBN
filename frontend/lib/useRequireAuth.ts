import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "./auth";

export function useRequireAuth() {
  const auth = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (auth.ready && !auth.isAuthenticated) {
      router.push("/login");
    }
  }, [auth.ready, auth.isAuthenticated, router]);

  // Pastikan me-return seluruh isi auth (termasuk .user)
  return auth; 
}