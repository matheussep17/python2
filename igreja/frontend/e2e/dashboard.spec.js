import { expect, test } from "@playwright/test";

async function mockApi(page) {
  await page.addInitScript(() => localStorage.setItem("igreja_access_token", "playwright-token"));
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const response = (body, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

    if (url.pathname.endsWith("/auth/me")) return response({ id: "user-1", tenant_id: "tenant-1", email: "admin@example.com", role: "owner" });
    if (url.pathname.endsWith("/events")) return response([]);
    if (url.pathname.endsWith("/members")) return response([{ id: "member-1", full_name: "Ana Souza", email: "ana@example.com", phone: "(11) 99999-9999", status: "active" }]);
    if (url.pathname.endsWith("/finance/summary")) return response({ period: "2026-09", income_cents: 0, expense_cents: 5000, net_cents: -5000, accounts: [{ id: "account-1", name: "Caixa", opening_balance_cents: 0, income_cents: 0, expense_cents: 5000, balance_cents: -5000 }] });
    if (url.pathname.endsWith("/finance/transactions")) return response([]);
    if (url.pathname.endsWith("/finance/accounts")) return response([{ id: "account-1", name: "Caixa", opening_balance_cents: 0, active: 1 }]);
    if (url.pathname.endsWith("/finance/categories")) return response([{ id: "category-income", name: "Dízimos", kind: "income", active: 1 }, { id: "category-expense", name: "Aluguel", kind: "expense", active: 1 }]);
    return response({});
  });
}

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await page.goto("/");
});

test("exibe o dashboard e destaca saldo negativo", async ({ page }) => {
  await expect(page.getByRole("heading", { name: "Visão geral" })).toBeVisible();
  await expect(page.getByText("Saldo total")).toBeVisible();
  const negativeBalances = page.locator(".negative-balance");
  await expect(negativeBalances).toHaveCount(2);
  await expect(negativeBalances.first()).toHaveText(/-R\$\s*50,00/);
});

test("navega para membros e mostra validação antes do envio", async ({ page }) => {
  await page.getByRole("button", { name: "Membros" }).click();
  await page.getByRole("button", { name: "Adicionar membro" }).click();
  const email = page.getByPlaceholder("membro@exemplo.com");
  await email.fill("email-invalido");
  await expect(page.getByText("Informe um e-mail válido.")).toBeVisible();
  await expect(email).toHaveAttribute("aria-invalid", "true");
});

test("exibe Entrada e Saída no fluxo financeiro", async ({ page }) => {
  await page.getByRole("button", { name: "Financeiro" }).click();
  const categoryType = page.getByRole("combobox", { name: "Tipo da categoria" });
  await expect(categoryType.locator("option[value='income']")).toHaveText("Entrada");
  await expect(categoryType.locator("option[value='expense']")).toHaveText("Saída");
  await page.getByRole("button", { name: "Novo lançamento" }).click();
  await expect(page.getByRole("option", { name: "Entrada" }).last()).toBeAttached();
  await expect(page.getByRole("option", { name: "Saída" }).last()).toBeAttached();
});