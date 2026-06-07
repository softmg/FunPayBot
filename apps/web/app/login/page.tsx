import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/auth";
import LoginForm from "./login-form";

export default async function LoginPage() {
  const user = await getCurrentUser();
  if (user) {
    redirect("/");
  }

  return (
    <main className="main" style={{ maxWidth: 460 }}>
      <div className="panel">
        <h1>FunPayBot</h1>
        <p className="muted">Sign in to manage searches, purchases, and account records.</p>
        <LoginForm />
      </div>
    </main>
  );
}

