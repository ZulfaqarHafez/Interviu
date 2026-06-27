import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Interviu",
  description: "Candidate evaluation with TraceRazor proof"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
