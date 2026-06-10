"use client";
import { useEffect, useState } from "react";

export function useIsMobile() {
  const [m, setM] = useState(false);
  useEffect(() => {
    const c = () => setM(window.innerWidth < 768);
    c(); window.addEventListener("resize", c);
    return () => window.removeEventListener("resize", c);
  }, []);
  return m;
}

export function useIsTablet() {
  const [t, setT] = useState(false);
  useEffect(() => {
    const c = () => setT(window.innerWidth >= 768 && window.innerWidth < 1024);
    c(); window.addEventListener("resize", c);
    return () => window.removeEventListener("resize", c);
  }, []);
  return t;
}
