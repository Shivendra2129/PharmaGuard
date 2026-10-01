import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PharmaGuard – Intelligent Multi-Gene Pharmacogenomic Risk Prediction",
  description:
    "An Intelligent VCF-Based Multi-Gene Pharmacogenomic Risk Prediction System. " +
    "Deterministic CPIC rules engine with dual-tier AI explainability. " +
    "Upload VCF files and receive drug safety predictions for CYP2D6, CYP2C19, CYP2C9, SLCO1B1, TPMT, DPYD.",
  keywords: [
    "pharmacogenomics", "VCF", "CPIC", "drug safety", "AI", "genomics",
    "CYP2D6", "CYP2C19", "TPMT", "DPYD", "diplotype", "precision medicine"
  ],

  openGraph: {
    title: "PharmaGuard – Intelligent Multi-Gene Pharmacogenomic Risk Prediction",
    description:
      "Deterministic CPIC risk engine + dual-tier LLM explainability for 6 pharmacogenes",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={inter.variable}>
      <body className="antialiased bg-gray-950 text-gray-100 min-h-screen">
        {children}
      </body>
    </html>
  );
}
