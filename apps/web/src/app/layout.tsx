import "./globals.css";
import "./motion.css";

export const metadata = {
  title: { default: "JobSeeker Intelligence", template: "%s | JobSeeker Intelligence" },
  description: "A focused career operations workspace for discovering opportunities, managing applications and making better career decisions.",
  applicationName: "JobSeeker Intelligence",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return <html lang="en"><body>{children}</body></html>;
}
