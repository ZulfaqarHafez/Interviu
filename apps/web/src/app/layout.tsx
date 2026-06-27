import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { Toaster } from "@/components/Toaster";
import { AnnouncerProvider } from "@/components/announcer";

export const metadata: Metadata = {
  title: "Interviu",
  description: "Candidate evaluation with TraceRazor proof",
  icons: {
    icon: "/brand/interviu-mark.svg"
  }
};

const themeInitScript = `(function(){try{var t=localStorage.getItem('interviu-theme');if(!t){t=window.matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';}if(t==='dark'){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body>
        <Providers>
          <AnnouncerProvider>
            {children}
            <Toaster />
          </AnnouncerProvider>
        </Providers>
      </body>
    </html>
  );
}
