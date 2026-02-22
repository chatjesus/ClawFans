import type { Metadata } from "next";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import Sidebar from "@/components/Sidebar";
import { I18nProvider } from "@/contexts/I18nContext";

export const metadata: Metadata = {
  title: "ClawFans — Uncensored AI Companions",
  description: "Private, uncensored AI character chat. Powered by local LLM.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en" className="dark">
        <body className="antialiased font-sans">
          <I18nProvider>
            <div className="flex h-screen overflow-hidden">
              <Sidebar />
              <main className="flex-1 overflow-hidden">
                {children}
              </main>
            </div>
          </I18nProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
