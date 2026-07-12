import type { Metadata } from "next";

import "./globals.css";
import { SessionProvider } from "@/components/auth/session";

export const metadata: Metadata = {
  title: "Shiplog",
  description: "Draft, publish, and broadcast release notes.",
};

// Set the theme class before first paint to avoid a flash.
const themeScript = `(function(){try{var t=localStorage.getItem('shiplog.theme');var m=window.matchMedia('(prefers-color-scheme: dark)').matches;if(t==='dark'||(t!=='light'&&m)){document.documentElement.classList.add('dark');}}catch(e){}})();`;

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>
        <SessionProvider>{children}</SessionProvider>
      </body>
    </html>
  );
}
