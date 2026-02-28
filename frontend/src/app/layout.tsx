import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fast Food Sales Forecast",
  description: "ML-powered sales forecasting",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-gray-950 text-gray-100 min-h-screen">
        <nav className="border-b border-gray-800 px-6 py-3 flex items-center gap-6">
          <span className="font-semibold text-white">SalesForecast</span>
          <Link
            href="/dashboard"
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Dashboard
          </Link>
          <Link
            href="/agents"
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Agent
          </Link>
        </nav>
        <main className="p-6">{children}</main>
      </body>
    </html>
  );
}
