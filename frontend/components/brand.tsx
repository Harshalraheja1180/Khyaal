import { HeartHandshake } from "lucide-react";
export function Brand({ light = false }: { light?: boolean }) { return <div className="brand" style={light ? { color: "white" } : undefined}><span className="brand-mark"><HeartHandshake size={20}/></span><span>Khyaal</span></div>; }
