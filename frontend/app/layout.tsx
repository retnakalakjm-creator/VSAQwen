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
      <body>
        <a
          href="/legends"
          style={{
            position: "fixed",
            right: "1rem",
            top: "1rem",
            zIndex: 50,
            borderRadius: "999px",
            border: "1px solid rgba(148, 163, 184, 0.45)",
            background: "rgba(255, 255, 255, 0.92)",
            boxShadow: "0 12px 30px rgba(15, 23, 42, 0.12)",
            color: "#0f172a",
            fontSize: "0.78rem",
            fontWeight: 700,
            letterSpacing: "0.02em",
            padding: "0.55rem 0.8rem",
            textDecoration: "none",
          }}
        >
          Plain-English Legends
        </a>
        {children}
      </body>
    </html>
  );
}
