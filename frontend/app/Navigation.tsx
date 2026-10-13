"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const links = [["/", "总览", "◫"], ["/topics", "我的主题", "◎"], ["/digests", "情报简报", "▤"]];
export default function Navigation() {
  const path = usePathname();
  return <aside className="border-b border-line bg-surface lg:fixed lg:inset-y-0 lg:left-0 lg:z-20 lg:flex lg:w-56 lg:flex-col lg:border-b-0 lg:border-r">
    <Link href="/" className="flex items-center gap-3 px-5 py-6 lg:px-7 lg:py-9">
      <svg width="30" height="30" viewBox="0 0 32 32" fill="none" aria-hidden="true"><circle cx="16" cy="16" r="13" stroke="currentColor" strokeWidth="1.5"/><circle cx="16" cy="16" r="7" stroke="currentColor" opacity=".35"/><path d="M16 16L25 7M16 3V7M3 16H7" stroke="currentColor" strokeWidth="1.5"/><circle cx="16" cy="16" r="2" fill="currentColor"/></svg>
      <span><span className="block text-lg font-semibold tracking-tight">SignalRadar</span><span className="eyebrow text-[9px]">个人情报工作台</span></span>
    </Link>
    <nav aria-label="主导航" className="flex flex-wrap gap-1 px-3 pb-3 lg:flex-col lg:px-4">
      {links.map(([href, label, symbol]) => <Link key={href} href={href} aria-current={path === href ? "page" : undefined} className={`flex items-center gap-3 rounded-lg px-4 py-3 text-sm ${path === href ? "bg-accent-soft font-semibold text-accent" : "text-muted hover:bg-canvas"}`}><span aria-hidden="true" className="text-lg">{symbol}</span>{label}</Link>)}
      <Link href="/#system-status" className="flex items-center gap-3 rounded-lg px-4 py-3 text-sm text-muted hover:bg-canvas"><span aria-hidden="true">◉</span>系统状态</Link>
    </nav>
    <div className="mt-auto hidden border-t border-line p-6 lg:block"><span className="badge badge-active">本地工作空间</span><p className="mt-3 text-xs leading-6 text-muted">你的信息，在本机整理。<br/>v0.1.1 · 单用户版本</p></div>
  </aside>;
}
