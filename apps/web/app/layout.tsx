import "./globals.css";

export const metadata = {
  title: "FunPayBot",
  description: "Procurement automation panel"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

