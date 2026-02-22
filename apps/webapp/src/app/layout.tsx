import type { Metadata } from "next";
import "./globals.css";
import Header from "@/components/Header";
import Footer from "@/components/Footer";

const fontVariables = "font-sans";

export const metadata: Metadata = {
    title: "Ultiplate - Ultimate Boilerplate",
    description: "AI-native template for any project with deployment ready setup",
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en" suppressHydrationWarning>
            <head>
                <script
                    dangerouslySetInnerHTML={{
                        __html: `(function(){var t=localStorage.getItem("theme");var d=window.matchMedia("(prefers-color-scheme: dark)").matches;var v=t||(d?"dark":"light");document.documentElement.classList.add(v);})();`,
                    }}
                />
            </head>
            <body className={`${fontVariables} antialiased`}>
                <Header />
                <main className="min-h-screen">
                    {children}
                </main>
                <Footer />
            </body>
        </html>
    );
}
