import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import Navigation from "./Navigation";

export const metadata: Metadata = { title: "SignalRadar · 个人情报工作台", description: "关注主题、整理信息、阅读 AI 情报简报。" };
export default function RootLayout({ children }: { children: ReactNode }) {
  return <html lang="zh-CN"><body><a href="#main-content" className="sr-only focus:not-sr-only">跳转到正文</a><Navigation/><div className="min-w-0 lg:ml-56">{children}</div></body></html>;
}
