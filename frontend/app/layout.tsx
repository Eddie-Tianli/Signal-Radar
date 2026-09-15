import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import Navigation from "./Navigation";

export const metadata: Metadata = {
  title: "SignalRadar",
  description: "Personal Information Intelligence Platform",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body><a href="#main-content" className="sr-only focus:not-sr-only">Skip to content</a><Navigation />{children}</body>
    </html>
  );
}
