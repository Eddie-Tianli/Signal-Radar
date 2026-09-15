import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import Navigation from "./Navigation";

export const metadata: Metadata = {
  title: "SignalRadar",
  description: "个人信息情报平台",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="zh-CN">
      <body><a href="#main-content" className="sr-only focus:not-sr-only">跳转到正文</a><Navigation />{children}</body>
    </html>
  );
}
