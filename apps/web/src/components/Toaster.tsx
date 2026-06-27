"use client";

import { Toaster as SonnerToaster } from "sonner";

/** App-wide toast surface. Mounted once in the root layout. */
export function Toaster() {
  return <SonnerToaster richColors position="top-right" />;
}

export default Toaster;
