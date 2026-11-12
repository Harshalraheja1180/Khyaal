"use client";
import { useEffect } from "react";
export function Notice({ message, close }: { message: string; close: () => void }) { useEffect(() => { const id = window.setTimeout(close, 3800); return () => window.clearTimeout(id); }, [message, close]); return <div role="status" className="toast">{message}</div>; }
