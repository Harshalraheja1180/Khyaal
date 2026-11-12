"use client";
import { useEffect, useState } from "react";
import Image from "next/image";
import { mediaUrl } from "@/lib/api";
export function MediaImage({ id, alt, className }: { id?: string | null; alt: string; className?: string }) {
  const [url, setUrl] = useState("");
  useEffect(() => { let objectUrl = ""; if (id) void mediaUrl(id).then((value) => { objectUrl = value; setUrl(value); }).catch(() => setUrl("")); return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); }; }, [id]);
  return url ? <Image src={url} alt={alt} width={440} height={440} unoptimized className={className || "photo-tile"}/> : <div aria-label={alt} className={className || "photo-tile"} style={{display:"grid",placeItems:"center",color:"#6c8781"}}><span aria-hidden="true">✿</span></div>;
}
