import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Whittle CFD Planner",
  description: "Typed drone CFD planning console"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
