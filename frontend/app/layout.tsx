import type { Metadata } from "next";
import "./globals.css";
import Sidebar from "@/components/layout/Sidebar";
import Topbar from "@/components/layout/Topbar";
import BottomNav from "@/components/layout/BottomNav";
import { AppProvider } from "@/contexts/AppContext";
import StockPoolModal from "@/components/StockPoolModal";

export const metadata: Metadata = {
  title: "台股AI雷達",
  description: "Taiwan AI Stock Radar",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "台股AI雷達",
  },
  themeColor: "#0a0a12",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-TW" suppressHydrationWarning>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet" />
      </head>
      <body>
        <AppProvider>
          <div style={{ display: "flex", height: "100vh", overflow: "hidden" }}>
            {/* Desktop sidebar — hidden on mobile via CSS */}
            <div className="desktop-sidebar">
              <Sidebar />
            </div>

            <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
              <Topbar />
              <main
                className="main-scroll"
                style={{ flex: 1, overflowY: "auto", padding: 16, background: "var(--c-bg-main)" }}
              >
                {children}
              </main>
            </div>
          </div>

          {/* Mobile bottom navigation */}
          <BottomNav />

          {/* Global modals */}
          <StockPoolModal />
        </AppProvider>
      </body>
    </html>
  );
}
