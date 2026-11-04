import { redirect } from "next/navigation";

export default function LegacyWorkspaceRoute() {
  redirect("/dashboard");
}
