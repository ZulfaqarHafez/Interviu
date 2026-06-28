import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Toaster } from "@/components/Toaster";
import { AnnouncerProvider } from "@/components/announcer";
import { TopNav } from "@/components/workspace/TopNav";

// Self-hosted via next/font (no FOUT, no render-blocking @import). Inter carries
// the body; Space Grotesk is the "Litmus Lab" display face for headings/wordmark.
const inter = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
  weight: ["400", "500", "600", "700", "800"]
});

const display = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-display",
  display: "swap",
  weight: ["500", "600", "700"]
});

export const metadata: Metadata = {
  metadataBase: new URL("https://assay.dev"),
  title: "Assay: litmus test for AI agents",
  description: "Bring your agent.md. Find out where it breaks before you ship.",
  icons: {
    icon: [{ url: "/icon.png", type: "image/png" }]
  },
  openGraph: {
    title: "Assay: litmus test for AI agents",
    description: "Bring your agent.md. Find out where it breaks before you ship.",
    type: "website",
    images: [{ url: "/brand/assay-og.png", width: 1200, height: 630, alt: "Assay: litmus test for AI agents" }]
  },
  twitter: {
    card: "summary_large_image",
    title: "Assay: litmus test for AI agents",
    description: "Bring your agent.md. Find out where it breaks before you ship.",
    images: ["/brand/assay-og.png"]
  }
};

const themeInitScript = `(function(){try{var t=localStorage.getItem('assay-theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className={`${inter.variable} ${display.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>
          <AnnouncerProvider>
            <TopNav />
            {children}
            <Toaster />
          </AnnouncerProvider>
        </Providers>
      </body>
    </html>
  );
}
