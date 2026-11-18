import type { Metadata, Viewport } from "next";
import "./globals.css";

// Every page is rendered per request, so each response's scripts carry the nonce from
// its Content-Security-Policy (see src/proxy.ts).
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "CramPlan",
  description: "A day-by-day cram plan for one real event, by one fixed date.",
  applicationName: "CramPlan",
  appleWebApp: { capable: true, title: "CramPlan", statusBarStyle: "default" },
};

export const viewport: Viewport = {
  themeColor: "#1d4ed8",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="flex min-h-full flex-col">{children}</body>
    </html>
  );
}
