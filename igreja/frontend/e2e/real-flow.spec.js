import { expect, test } from "@playwright/test";

const API_URL = "http://127.0.0.1:8001";

async function createChurch(request) {
  await request.delete(`${API_URL}/api/v1/test/reset`);
  const unique = Date.now().toString();
  const church = await request.post(`${API_URL}/api/v1/tenants`, {
    data: { name: `Igreja E2E ${unique}`, owner_email: `owner-${unique}@example.com`, owner_password: "senha-e2e-segura" },
  });
  const churchData = await church.json();
  const login = await request.post(`${API_URL}/api/v1/auth/login`, {
    data: { tenant_id: churchData.id, email: `owner-${unique}@example.com`, password: "senha-e2e-segura" },
  });
  return { token: (await login.json()).access_token };
}

test.beforeEach(async ({ page, request }) => {
  const context = await createChurch(request);
  await page.addInitScript((token) => localStorage.setItem("igreja_access_token", token), context.token);
  await page.goto("/");
});

test.afterEach(async ({ request }) => {
  await request.delete(`${API_URL}/api/v1/test/reset`);
});

test("percorre cadastro, edição e inativação de membro", async ({ page }) => {
  await page.getByRole("button", { name: "Membros" }).click();
  await page.getByRole("button", { name: "Adicionar membro" }).click();
  await page.getByPlaceholder("Nome do membro").fill("Maria E2E");
  await page.getByPlaceholder("membro@exemplo.com").fill("maria@example.com");
  await page.getByPlaceholder("(00) 00000-0000").fill("11999999999");
  await page.getByRole("button", { name: "Salvar membro" }).click();
  await expect(page.getByText("Maria E2E")).toBeVisible();

  await page.getByRole("button", { name: "Editar Maria E2E" }).click();
  await page.getByPlaceholder("Nome do membro").fill("Maria Atualizada");
  await page.getByRole("button", { name: "Salvar alterações" }).click();
  await expect(page.getByText("Maria Atualizada")).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Inativar Maria Atualizada" }).click();
  await expect(page.getByText("Nenhum membro encontrado.")).toBeVisible();
});

test("cria e cancela um evento sem registrar presença", async ({ page }) => {
  await page.getByRole("button", { name: "Eventos" }).click();
  await page.getByRole("button", { name: "Novo evento" }).click();
  await page.getByPlaceholder("Culto de domingo").fill("Culto E2E");
  await page.locator(".event-form input[type='datetime-local']").first().fill("2026-10-10T19:00");
  await page.getByPlaceholder("Templo principal").fill("Templo E2E");
  await page.getByRole("button", { name: "Salvar evento" }).click();
  await expect(page.getByText("Culto E2E")).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByText("Nenhum evento agendado.")).toBeVisible();
});

test("cria conta, categorias e registra entrada e saída", async ({ page }) => {
  await page.getByRole("button", { name: "Financeiro" }).click();
  await page.getByPlaceholder("Conta bancária").fill("Caixa E2E");
  const accountResponse = page.waitForResponse((response) => response.url().endsWith("/api/v1/finance/accounts") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Criar conta" }).click();
  await expect((await accountResponse).ok()).toBeTruthy();
  await page.getByPlaceholder("Dízimos, aluguel...").fill("Dízimos E2E");
  const incomeCategoryResponse = page.waitForResponse((response) => response.url().endsWith("/api/v1/finance/categories") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Criar categoria" }).click();
  await expect((await incomeCategoryResponse).ok()).toBeTruthy();
  await page.getByPlaceholder("Dízimos, aluguel...").fill("Aluguel E2E");
  await page.getByLabel("Tipo da categoria").selectOption("expense");
  const expenseCategoryResponse = page.waitForResponse((response) => response.url().endsWith("/api/v1/finance/categories") && response.request().method() === "POST");
  await page.getByRole("button", { name: "Criar categoria" }).click();
  expect((await (await expenseCategoryResponse).json()).kind).toBe("expense");

  await page.getByRole("button", { name: "Novo lançamento" }).click();
  const form = page.locator(".finance-form");
  await form.locator("select").nth(1).selectOption({ label: "Caixa E2E" });
  await form.locator("select").nth(2).selectOption({ label: "Dízimos E2E" });
  await form.locator("input[type='number']").fill("100");
  await form.getByPlaceholder("Dízimo, aluguel...").fill("Entrada E2E");
  await form.getByRole("button", { name: "Registrar" }).click();

  await page.getByRole("button", { name: "Novo lançamento" }).click();
  const expenseForm = page.locator(".finance-form");
  await expenseForm.locator("select").nth(0).selectOption("expense");
  await expect(expenseForm.getByRole("option", { name: "Aluguel E2E" })).toBeAttached();
  await expenseForm.locator("select").nth(1).selectOption({ label: "Caixa E2E" });
  await expenseForm.locator("select").nth(2).selectOption({ label: "Aluguel E2E" });
  await expenseForm.locator("input[type='number']").fill("25");
  await expenseForm.getByPlaceholder("Dízimo, aluguel...").fill("Saída E2E");
  await expenseForm.getByRole("button", { name: "Registrar" }).click();
  await expect(page.locator(".transaction-row").filter({ hasText: "Entrada E2E" })).toBeVisible();
  await expect(page.locator(".transaction-row").filter({ hasText: "Saída E2E" })).toBeVisible();
});