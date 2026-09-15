"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

export default function Navigation() {
  const path = usePathname();
  return <header className="border-b border-slate-200 bg-white">
    <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4 sm:px-8">
      <Link href="/" className="flex items-center gap-3 font-bold tracking-tight text-slate-900">
        <span aria-hidden="true" className="rounded-lg bg-slate-900 px-2 py-1 text-white">SR</span>
        SignalRadar <span className="text-xs font-normal text-slate-500">LOCAL · v0.1.0</span>
      </Link>
      <nav aria-label="Main navigation" className="flex gap-2">
        {[['/', 'Dashboard'], ['/topics', 'Topics']].map(([href, label]) => <Link key={href} href={href}
          aria-current={path === href ? "page" : undefined}
          className={`rounded-lg px-4 py-2 text-sm font-medium ${path === href ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{label}</Link>)}
      </nav>
    </div>
  </header>;
}
