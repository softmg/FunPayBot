import "./globals.css";

export const metadata = {
  title: "FunPayBot",
  description: "Панель автоматизации закупок"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}
