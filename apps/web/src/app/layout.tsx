import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Shuttle Flux — AI Badminton Match Analytics",
  description: "Next-generation computer vision analytics for badminton matches: automated tracking, 2D radar court, and tactical insights.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-background text-gray-100 antialiased selection:bg-brand-cyan selection:text-black">
        {children}
      </body>
    </html>
  );
}
