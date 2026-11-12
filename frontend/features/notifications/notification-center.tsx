"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { api, Notification } from "@/lib/api";

export function NotificationCenter({ onRelationshipClick }: { onRelationshipClick: () => void }) {
  const [items, setItems] = useState<Notification[]>([]);
  const [unread, setUnread] = useState(0);
  const [open, setOpen] = useState(false);
  const [loadError, setLoadError] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [notifications, count] = await Promise.all([
        api<Notification[]>("/notifications?limit=40"),
        api<{ unread_count: number }>("/notifications/unread-count"),
      ]);
      setItems(notifications);
      setUnread(count.unread_count);
      setLoadError(false);
    } catch {
      setLoadError(true);
    }
  }, []);

  useEffect(() => {
    const refreshIfVisible = () => { if (document.visibilityState === "visible") void refresh(); };
    const timer = window.setTimeout(() => void refresh(), 0);
    const interval = window.setInterval(refreshIfVisible, 45_000);
    window.addEventListener("focus", refreshIfVisible);
    document.addEventListener("visibilitychange", refreshIfVisible);
    return () => {
      window.clearTimeout(timer);
      window.clearInterval(interval);
      window.removeEventListener("focus", refreshIfVisible);
      document.removeEventListener("visibilitychange", refreshIfVisible);
    };
  }, [refresh]);

  async function markRead(item: Notification) {
    try {
      if (!item.is_read) {
        const updated = await api<Notification>(`/notifications/${item.id}/read`, { method: "PATCH" });
        setItems((current) => current.map((entry) => entry.id === updated.id ? updated : entry));
        setUnread((count) => Math.max(0, count - 1));
      }
      setOpen(false);
      if (item.guardian_link_id || item.notification_type.startsWith("guardian_link.")) onRelationshipClick();
    } catch {
      setLoadError(true);
    }
  }

  async function markAllRead() {
    try {
      await api("/notifications/read-all", { method: "POST" });
      setItems((current) => current.map((item) => ({ ...item, is_read: true })));
      setUnread(0);
    } catch {
      setLoadError(true);
    }
  }

  return <div className="notification-center">
    <button
      className="notification-trigger"
      type="button"
      aria-label={unread ? `Notifications, ${unread} unread` : "Notifications"}
      aria-expanded={open}
      aria-haspopup="dialog"
      onClick={() => { setOpen((current) => !current); if (!open) void refresh(); }}
    >
      <Bell size={20} aria-hidden="true" />
      {unread > 0 && <span className="notification-count" aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}
    </button>
    {open && <section className="notification-panel" role="dialog" aria-label="Notifications">
      <div className="notification-panel-head"><div><strong>Notifications</strong><div className="muted" style={{ fontSize: 12 }}>{unread} unread</div></div><button className="btn small secondary" type="button" onClick={() => void markAllRead()} disabled={!unread}><CheckCheck size={15} /> Mark all read</button></div>
      {loadError && <p className="notification-error" role="status">Notifications could not be updated. Please try again.</p>}
      <div className="notification-list">
        {items.map((item) => <button
          className={`notification-item ${item.is_read ? "read" : "unread"}`}
          type="button"
          key={item.id}
          onClick={() => void markRead(item)}
        >
          <span className="notification-dot" aria-hidden="true" />
          <span className="notification-copy"><strong>{item.title}</strong><span>{item.message}</span><time dateTime={item.created_at}>{new Date(item.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })}</time></span>
        </button>)}
        {!items.length && !loadError && <p className="notification-empty">You’re all caught up.</p>}
      </div>
    </section>}
  </div>;
}
