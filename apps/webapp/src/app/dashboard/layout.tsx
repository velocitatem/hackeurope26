import "./dashboard.css";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <div className="dashboard-shell">{children}</div>;
}
