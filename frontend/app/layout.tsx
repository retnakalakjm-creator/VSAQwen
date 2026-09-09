import type { Metadata } from "next";
import "./globals.css";
import "./vsa-timeline.css";
import "./readable-ui.css";
import "./trader-readable-ui.css";

export const metadata: Metadata = {
  title: "ProVSA Command Centre",
  description: "VSA market analysis command centre",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
