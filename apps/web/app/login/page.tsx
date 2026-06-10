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
        <p className="muted">Войдите, чтобы управлять поиском, закупками и базой аккаунтов.</p>
        <LoginForm />
      </div>
    </main>
  );
}
