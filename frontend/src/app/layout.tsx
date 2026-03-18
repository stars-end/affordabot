import type { Metadata } from "next";
import { Public_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { Sidebar } from "../components/Sidebar";
import { Toaster } from "@/components/ui/sonner";
import { ClerkWrapper } from "./clerk-wrapper";

export const dynamic = 'force-dynamic';

const publicSans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-numbers",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AffordaBot",
  description: "AI-powered legislation analysis",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${publicSans.variable} ${jetbrainsMono.variable} font-sans antialiased bg-white`}>
        <ClerkWrapper>
          <div className="rainbow-gradient h-[3px] w-full fixed top-0 left-0 right-0 z-50" />
          <div className="min-h-screen bg-white pt-[3px]">
            <div className="flex">
              <Sidebar />
              <main className="flex-1 p-6">{children}</main>
            </div>
            <Toaster />
          </div>
        </ClerkWrapper>
      </body>
    </html>
  );
}
