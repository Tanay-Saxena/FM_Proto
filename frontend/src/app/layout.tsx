import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, Figtree, Young_Serif, Fraunces } from "next/font/google";
import "./globals.css";
import { Providers } from "@/components/providers";

const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"], axes: ["opsz", "wdth"] });
const body = Figtree({ variable: "--font-body", subsets: ["latin"] });
const flair = Fraunces({ variable: "--font-flair", subsets: ["latin"], style: ["italic"], axes: ["SOFT", "WONK", "opsz"] });
const serif = Young_Serif({ variable: "--font-serif", subsets: ["latin"], weight: "400" });

export const metadata: Metadata = {
  title: { default: "FoodMania — scan, discover, order, pay", template: "%s · FoodMania" },
  description: "QR menus with honest AI food discovery, live availability, kitchen tickets and digital receipts for restaurants.",
};
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#12372a" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${serif.variable} ${flair.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
