import type { Metadata } from "next";
import { Public_Sans, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ClerkProvider } from "@clerk/nextjs";
import { Sidebar } from "../components/Sidebar";
import { Toaster } from "@/components/ui/sonner";

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

const clerkJSVersion = process.env.NEXT_PUBLIC_CLERK_JS_VERSION ?? "5.117.0";

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
    <ClerkProvider clerkJSVersion={clerkJSVersion}>
      <html lang="en">
        <body className={`${publicSans.variable} ${jetbrainsMono.variable} font-sans antialiased bg-white`}>
          {/* Rainbow gradient bar at top */}
          <div className="rainbow-gradient h-[3px] w-full fixed top-0 left-0 right-0 z-50" />

          <div className="min-h-screen bg-white pt-[3px]">
            <div className="flex">
              <Sidebar />
              <main className="flex-1 p-6">{children}</main>
            </div>
            <Toaster />
          </div>
        </body>
      </html>
    </ClerkProvider>
  );
}
