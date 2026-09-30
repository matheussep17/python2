import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  CircleDollarSign,
  LayoutDashboard,
  LogOut,
  Menu,
  Pencil,
  Trash2,
  Users,
  WalletCards,
  X,
} from "lucide-react";
import { formatPhone, validateMemberForm } from "./validation.js";

const API_URL = import.meta.env.VITE_API_URL || (window.location.port === "5180" ? "http://127.0.0.1:8001" : "http://127.0.0.1:8000");
const monthFormatter = new Intl.DateTimeFormat("pt-BR", { month: "long", year: "numeric" });
const moneyFormatter = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

function currentPeriod() {
  return new Date().toISOString().slice(0, 7);
}

function formatMoney(cents) {
  if (cents === null || cents === undefined) return "—";
  return moneyFormatter.format((cents || 0) / 100);
}

function formatDate(value) {
  return new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short" }).format(new Date(value));
}

async function request(path, options = {}) {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Não foi possível concluir a solicitação.");
  }
  return response.status === 204 ? null : response.json();
}

function LoginScreen({ onLogin }) {
  const [form, setForm] = useState({ tenant_id: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setLoading(true);
    try {
      const result = await request("/api/v1/auth/login", { method: "POST", body: JSON.stringify(form) });
      localStorage.setItem("igreja_access_token", result.access_token);
      onLogin(result.access_token);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-shell">
      <section className="login-aside">
        <div className="brand-mark">C</div>
        <p className="eyebrow">Igreja SaaS</p>
        <h1>Administre o que importa.</h1>
        <p className="aside-copy">Pessoas, encontros e recursos da sua comunidade em um só lugar.</p>
        <div className="aside-note"><span>01</span><span>Uma visão mais clara para cada semana.</span></div>
      </section>
      <section className="login-panel">
        <div className="login-form-wrap">
          <p className="eyebrow">Área da igreja</p>
          <h2>Entrar no painel</h2>
          <p className="muted">Use as credenciais do seu administrador.</p>
          <form onSubmit={submit} className="form-stack">
            <label>ID da igreja<input required value={form.tenant_id} onChange={(event) => setForm({ ...form, tenant_id: event.target.value })} placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" /></label>
            <label>E-mail<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} placeholder="voce@igreja.com" /></label>
            <label>Senha<input required type="password" value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} placeholder="Sua senha" /></label>
            {error && <p className="form-error">{error}</p>}
            <button className="primary-button" disabled={loading}>{loading ? "Entrando..." : "Acessar painel"}<ArrowUpRight size={17} /></button>
          </form>
        </div>
      </section>
    </main>
  );
}

function FinanceSetup({ authHeaders, onAccountCreated, onCategoryCreated }) {
  const [accountName, setAccountName] = useState("");
  const [categoryName, setCategoryName] = useState("");
  const [categoryKind, setCategoryKind] = useState("income");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function createAccount(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const account = await request("/api/v1/finance/accounts", { method: "POST", headers: authHeaders, body: JSON.stringify({ name: accountName, opening_balance_cents: 0 }) });
      onAccountCreated(account);
      setAccountName("");
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }

  async function createCategory(event) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const category = await request("/api/v1/finance/categories", { method: "POST", headers: authHeaders, body: JSON.stringify({ name: categoryName, kind: categoryKind }) });
      onCategoryCreated(category);
      setCategoryName("");
    } catch (requestError) { setError(requestError.message); } finally { setSaving(false); }
  }

  return <div className="finance-setup"><div><p className="eyebrow warm">CONFIGURAÇÃO INICIAL</p><h3>Prepare o financeiro</h3><p className="muted">A conta é neutra. O tipo Entrada ou Saída é definido pela categoria do lançamento.</p></div><div className="setup-forms"><form className="account-form" onSubmit={createAccount}><label>Conta<input required minLength="2" value={accountName} onChange={(event) => setAccountName(event.target.value)} placeholder="Conta bancária" /></label><button className="secondary-button" disabled={saving}>Criar conta</button></form><form className="category-form" onSubmit={createCategory}><label>Categoria<input required minLength="2" value={categoryName} onChange={(event) => setCategoryName(event.target.value)} placeholder="Dízimos, aluguel..." /></label><label>Tipo<select aria-label="Tipo da categoria" value={categoryKind} onChange={(event) => setCategoryKind(event.target.value)}><option value="income">Entrada</option><option value="expense">Saída</option></select></label><button className="secondary-button" disabled={saving}>Criar categoria</button></form></div>{error && <small className="field-error">{error}</small>}</div>;
}

function Dashboard({ token, onLogout }) {
  const [user, setUser] = useState(null);
  const [summary, setSummary] = useState(null);
  const [events, setEvents] = useState([]);
  const [members, setMembers] = useState([]);
  const [memberSearch, setMemberSearch] = useState("");
  const [transactions, setTransactions] = useState([]);
  const [financeAccounts, setFinanceAccounts] = useState([]);
  const [financeCategories, setFinanceCategories] = useState([]);
  const [showFinanceForm, setShowFinanceForm] = useState(false);
  const [financeForm, setFinanceForm] = useState({ account_id: "", category_id: "", kind: "income", amount: "", description: "", occurred_on: new Date().toISOString().slice(0, 10) });
  const [financeSaving, setFinanceSaving] = useState(false);
  const [showMemberForm, setShowMemberForm] = useState(false);
  const [memberForm, setMemberForm] = useState({ full_name: "", email: "", phone: "" });
  const [memberErrors, setMemberErrors] = useState({});
  const [editingMemberId, setEditingMemberId] = useState(null);
  const [memberSaving, setMemberSaving] = useState(false);
  const [showEventForm, setShowEventForm] = useState(false);
  const [eventForm, setEventForm] = useState({ title: "", starts_at: "", ends_at: "", location: "", description: "" });
  const [eventSaving, setEventSaving] = useState(false);
  const [attendanceEventId, setAttendanceEventId] = useState(null);
  const [attendance, setAttendance] = useState([]);
  const [attendanceMemberId, setAttendanceMemberId] = useState("");
  const [period, setPeriod] = useState(currentPeriod());
  const [activeSection, setActiveSection] = useState("dashboard");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);

  const authHeaders = { Authorization: `Bearer ${token}` };

  useEffect(() => {
    async function loadDashboard() {
      setLoading(true);
      setError("");
      try {
        const [me, upcomingEvents, churchMembers] = await Promise.all([
          request("/api/v1/auth/me", { headers: authHeaders }),
          request("/api/v1/events", { headers: authHeaders }),
          request("/api/v1/members", { headers: authHeaders }),
        ]);
        let finance = null;
        let financeTransactions = [];
        if (["owner", "admin"].includes(me.role)) {
          [finance, financeTransactions] = await Promise.all([
            request(`/api/v1/finance/summary?period=${period}`, { headers: authHeaders }),
            request(`/api/v1/finance/transactions?period=${period}`, { headers: authHeaders }),
          ]);
          const [accounts, categories] = await Promise.all([
            request("/api/v1/finance/accounts", { headers: authHeaders }),
            request("/api/v1/finance/categories", { headers: authHeaders }),
          ]);
          setFinanceAccounts(accounts);
          setFinanceCategories(categories);
        }
        setUser(me);
        setSummary(finance);
        setEvents(upcomingEvents.filter((event) => event.status === "scheduled").slice(0, 3));
        setMembers(churchMembers);
        setTransactions(financeTransactions);
      } catch (requestError) {
        if (requestError.message.includes("Sessão") || requestError.message.includes("Bearer")) onLogout();
        setError(requestError.message);
      } finally {
        setLoading(false);
      }
    }
    loadDashboard();
  }, [period, token]);

  if (loading && !summary) return <div className="loading-screen"><div className="loader" />Carregando seu painel</div>;

  function navigate(section) {
    setActiveSection(section);
    setMenuOpen(false);
  }

  async function addMember(event) {
    event.preventDefault();
    const validationErrors = validateMemberForm(memberForm);
    setMemberErrors(validationErrors);
    if (Object.keys(validationErrors).length) return;
    setMemberSaving(true);
    setError("");
    try {
      const member = await request("/api/v1/members", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          full_name: memberForm.full_name,
          email: memberForm.email || null,
          phone: memberForm.phone || null,
        }),
      });
      setMembers((current) => [...current, member].sort((first, second) => first.full_name.localeCompare(second.full_name)));
      setMemberForm({ full_name: "", email: "", phone: "" });
      setMemberErrors({});
      setShowMemberForm(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMemberSaving(false);
    }
  }

  function startEditingMember(member) {
    setEditingMemberId(member.id);
    setMemberForm({ full_name: member.full_name, email: member.email || "", phone: member.phone || "" });
    setMemberErrors({});
    setShowMemberForm(true);
    setError("");
  }

  async function saveMember(event) {
    event.preventDefault();
    const validationErrors = validateMemberForm(memberForm);
    setMemberErrors(validationErrors);
    if (Object.keys(validationErrors).length) return;
    setMemberSaving(true);
    setError("");
    try {
      const member = await request(`/api/v1/members/${editingMemberId}`, {
        method: "PATCH",
        headers: authHeaders,
        body: JSON.stringify({ full_name: memberForm.full_name, email: memberForm.email || null, phone: memberForm.phone || null }),
      });
      setMembers((current) => current.map((item) => item.id === member.id ? member : item));
      setEditingMemberId(null);
      setMemberForm({ full_name: "", email: "", phone: "" });
      setMemberErrors({});
      setShowMemberForm(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setMemberSaving(false);
    }
  }

  async function removeMember(member) {
    if (!window.confirm(`Inativar ${member.full_name}? O histórico será preservado.`)) return;
    setError("");
    try {
      await request(`/api/v1/members/${member.id}`, { method: "DELETE", headers: authHeaders });
      setMembers((current) => current.filter((item) => item.id !== member.id));
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  async function createEvent(event) {
    event.preventDefault();
    setEventSaving(true);
    setError("");
    try {
      const created = await request("/api/v1/events", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          ...eventForm,
          starts_at: new Date(eventForm.starts_at).toISOString(),
          ends_at: eventForm.ends_at ? new Date(eventForm.ends_at).toISOString() : null,
          description: eventForm.description || null,
          location: eventForm.location || null,
        }),
      });
      setEvents((current) => [created, ...current].slice(0, 3));
      setEventForm({ title: "", starts_at: "", ends_at: "", location: "", description: "" });
      setShowEventForm(false);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setEventSaving(false);
    }
  }

  async function createFinanceTransaction(event) {
    event.preventDefault();
    setFinanceSaving(true);
    setError("");
    try {
      const amountCents = Math.round(Number(String(financeForm.amount).replace(",", ".")) * 100);
      const transaction = await request("/api/v1/finance/transactions", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({ ...financeForm, amount_cents: amountCents, amount: undefined }),
      });
      setTransactions((current) => [transaction, ...current]);
      setShowFinanceForm(false);
      setFinanceForm({ ...financeForm, amount: "", description: "" });
      const refreshed = await request(`/api/v1/finance/summary?period=${period}`, { headers: authHeaders });
      setSummary(refreshed);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setFinanceSaving(false);
    }
  }

  async function cancelEvent(eventId) {
    if (!window.confirm("Cancelar este evento? O histórico será preservado.")) return;
    try {
      await request(`/api/v1/events/${eventId}`, { method: "DELETE", headers: authHeaders });
      setEvents((current) => current.filter((event) => event.id !== eventId));
      if (attendanceEventId === eventId) setAttendanceEventId(null);
    } catch (requestError) { setError(requestError.message); }
  }

  async function openAttendance(eventId) {
    setError("");
    try {
      const records = await request(`/api/v1/events/${eventId}/attendance`, { headers: authHeaders });
      setAttendanceEventId(eventId);
      setAttendance(records);
      setAttendanceMemberId("");
    } catch (requestError) { setError(requestError.message); }
  }

  async function markMemberAttendance(event) {
    event.preventDefault();
    if (!attendanceMemberId || !attendanceEventId) return;
    try {
      const record = await request(`/api/v1/events/${attendanceEventId}/attendance`, { method: "POST", headers: authHeaders, body: JSON.stringify({ member_id: attendanceMemberId, present: true }) });
      setAttendance((current) => [...current.filter((item) => item.member_id !== record.member_id), { ...record, full_name: members.find((member) => member.id === record.member_id)?.full_name || "Membro" }]);
      setAttendanceMemberId("");
    } catch (requestError) { setError(requestError.message); }
  }

  async function closePeriod() {
    if (!window.confirm(`Fechar a competência ${period}? Novos lançamentos nela serão bloqueados.`)) return;
    try {
      await request(`/api/v1/finance/periods/${period}/close`, { method: "POST", headers: authHeaders });
      setError("");
    } catch (requestError) { setError(requestError.message); }
  }

  async function reverseTransaction(transaction) {
    const reverseKind = transaction.kind === "income" ? "expense" : "income";
    const category = financeCategories.find((item) => item.kind === reverseKind);
    if (!category) {
      setError(`Crie uma categoria de ${reverseKind === "income" ? "entrada" : "saída"} para fazer o estorno.`);
      return;
    }
    if (!window.confirm(`Estornar ${transaction.description}?`)) return;
    try {
      const reversal = await request(`/api/v1/finance/transactions/${transaction.id}/reverse`, { method: "POST", headers: authHeaders, body: JSON.stringify({ category_id: category.id, occurred_on: new Date().toISOString().slice(0, 10) }) });
      setTransactions((current) => [reversal, ...current]);
      setError("");
    } catch (requestError) { setError(requestError.message); }
  }

  const sectionTitles = { dashboard: "Visão geral", members: "Membros", events: "Eventos", finance: "Financeiro" };
  const canViewFinance = ["owner", "admin"].includes(user?.role);
  const visibleMembers = members.filter((member) => `${member.full_name} ${member.email || ""} ${member.phone || ""}`.toLowerCase().includes(memberSearch.toLowerCase().trim()));
  const totalBalanceCents = summary?.accounts?.reduce((total, account) => total + account.balance_cents, 0) ?? null;

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "is-open" : ""}`}>
        <div className="sidebar-top"><div className="brand-mark small">C</div><button className="icon-button close-menu" onClick={() => setMenuOpen(false)} aria-label="Fechar menu"><X size={19} /></button></div>
        <div className="church-switcher"><span className="church-avatar">{user?.email?.[0]?.toUpperCase() || "I"}</span><span><strong>Minha igreja</strong><small>{user?.role || "admin"}</small></span><ChevronDown size={15} /></div>
        <nav className="nav-list">
          <button className={`nav-item ${activeSection === "dashboard" ? "active" : ""}`} onClick={() => navigate("dashboard")}><LayoutDashboard size={18} />Visão geral</button>
          <button className={`nav-item ${activeSection === "members" ? "active" : ""}`} onClick={() => navigate("members")}><Users size={18} />Membros</button>
          <button className={`nav-item ${activeSection === "events" ? "active" : ""}`} onClick={() => navigate("events")}><CalendarDays size={18} />Eventos</button>
          <button className={`nav-item ${activeSection === "finance" ? "active" : ""}`} onClick={() => navigate("finance")}><WalletCards size={18} />Financeiro</button>
        </nav>
        <div className="sidebar-bottom"><button className="nav-item logout-button" onClick={onLogout}><LogOut size={18} />Sair</button></div>
      </aside>
      {menuOpen && <button className="backdrop" onClick={() => setMenuOpen(false)} aria-label="Fechar menu" />}
      <main className="main-content">
        <header className="topbar"><button className="icon-button menu-button" onClick={() => setMenuOpen(true)} aria-label="Abrir menu"><Menu size={20} /></button><div><p className="eyebrow">Quarta-feira, 30 de setembro</p><h1>{sectionTitles[activeSection]}</h1></div><div className="topbar-user"><span className="status-dot" />{user?.email}</div></header>
        <section className="content-wrap">
          {activeSection === "dashboard" && <div className="welcome-row"><div><p className="eyebrow warm">PAINEL DA COMUNIDADE</p><h2>Bom dia, liderança.</h2><p className="muted">Aqui está o pulso da sua igreja neste momento.</p></div><label className="period-picker">Competência<input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label></div>}
          {error && <div className="notice error">{error}</div>}
          {activeSection === "finance" && canViewFinance && <FinanceSetup authHeaders={authHeaders} onAccountCreated={(account) => setFinanceAccounts((current) => [...current, account])} onCategoryCreated={(category) => setFinanceCategories((current) => [...current, category])} />}
          {activeSection === "finance" && canViewFinance && <div className="finance-period-action"><button className="secondary-button" onClick={closePeriod}>Fechar competência {period}</button></div>}
          {activeSection === "finance" && canViewFinance && transactions.length > 0 && <div className="finance-reversal-list"><p className="eyebrow">CORREÇÕES</p>{transactions.filter((transaction) => !transaction.reversal_of).map((transaction) => <div key={transaction.id}><span>{transaction.description}</span><button className="text-link" onClick={() => reverseTransaction(transaction)}>Estornar</button></div>)}</div>}
          {activeSection === "dashboard" && <><div className="metric-grid">
            <article className={`metric-card featured ${totalBalanceCents < 0 ? "negative-card" : ""}`}><div className="metric-label">Saldo total <CircleDollarSign size={17} /></div><strong className={totalBalanceCents < 0 ? "negative-balance" : ""}>{formatMoney(totalBalanceCents)}</strong><span className="metric-foot">Em todas as contas ativas</span></article>
            <article className="metric-card"><div className="metric-label">Entradas <span className="trend positive">+ mês</span></div><strong>{formatMoney(summary?.income_cents)}</strong><span className="metric-foot">Competência selecionada</span></article>
            <article className="metric-card"><div className="metric-label">Saídas <span className="trend neutral">mês</span></div><strong>{formatMoney(summary?.expense_cents)}</strong><span className="metric-foot">Competência selecionada</span></article>
            <article className="metric-card"><div className="metric-label">Resultado líquido <span className="trend positive">net</span></div><strong>{formatMoney(summary?.net_cents)}</strong><span className="metric-foot">Entradas menos saídas</span></article>
          </div><div className="dashboard-grid">
            <section className="panel accounts-panel"><div className="panel-heading"><div><p className="eyebrow">POSIÇÃO</p><h3>Contas financeiras</h3></div><button onClick={() => navigate("finance")} className="text-link">Ver detalhes <ArrowUpRight size={15} /></button></div><div className="account-list">{summary?.accounts?.map((account) => <div className="account-row" key={account.id}><span className="account-icon"><WalletCards size={17} /></span><span className="account-name"><strong>{account.name}</strong><small>Entradas {formatMoney(account.income_cents)} · Saídas {formatMoney(account.expense_cents)}</small></span><strong className={account.balance_cents < 0 ? "negative-balance" : ""}>{formatMoney(account.balance_cents)}</strong></div>)}</div></section>
            <section className="panel events-panel"><div className="panel-heading"><div><p className="eyebrow">AGENDA</p><h3>Próximos encontros</h3></div><button onClick={() => navigate("events")} className="text-link">Agenda <ArrowUpRight size={15} /></button></div>{events.length ? <div className="event-list">{events.map((event) => <div className="event-row" key={event.id}><time><strong>{new Date(event.starts_at).getDate()}</strong><small>{new Intl.DateTimeFormat("pt-BR", { month: "short" }).format(new Date(event.starts_at)).replace(".", "")}</small></time><span><strong>{event.title}</strong><small>{event.location || "Local não informado"}</small></span><span className="event-time">{formatDate(event.starts_at)}</span></div>)}</div> : <div className="empty-state">Nenhum evento agendado.</div>}</section>
          </div></>}
          {activeSection === "members" && <section className="section-view"><div className="section-heading"><div><p className="eyebrow warm">COMUNIDADE</p><h2>Membros ativos</h2><p className="muted">{members.length} pessoas cadastradas na sua igreja.</p></div><div className="section-actions"><input className="search-input" value={memberSearch} onChange={(event) => setMemberSearch(event.target.value)} placeholder="Buscar membro..." aria-label="Buscar membro" /><button className="primary-button" onClick={() => { setEditingMemberId(null); setMemberForm({ full_name: "", email: "", phone: "" }); setMemberErrors({}); setShowMemberForm((open) => !open); }}>{showMemberForm ? "Fechar formulário" : "Adicionar membro"} <ArrowUpRight size={16} /></button></div></div>{showMemberForm && <form className="inline-form" onSubmit={editingMemberId ? saveMember : addMember} noValidate><label className={memberErrors.full_name ? "has-error" : ""}>Nome completo<input required minLength="2" value={memberForm.full_name} onChange={(event) => { const value = event.target.value; setMemberForm({ ...memberForm, full_name: value }); setMemberErrors({ ...memberErrors, full_name: validateMemberForm({ ...memberForm, full_name: value }).full_name }); }} aria-invalid={Boolean(memberErrors.full_name)} placeholder="Nome do membro" />{memberErrors.full_name && <small className="field-error">{memberErrors.full_name}</small>}</label><label className={memberErrors.email ? "has-error" : ""}>E-mail<input type="email" value={memberForm.email} onChange={(event) => { const value = event.target.value; setMemberForm({ ...memberForm, email: value }); setMemberErrors({ ...memberErrors, email: validateMemberForm({ ...memberForm, email: value }).email }); }} aria-invalid={Boolean(memberErrors.email)} placeholder="membro@exemplo.com" />{memberErrors.email && <small className="field-error">{memberErrors.email}</small>}</label><label className={memberErrors.phone ? "has-error" : ""}>Telefone<input value={memberForm.phone} onChange={(event) => { const value = formatPhone(event.target.value); setMemberForm({ ...memberForm, phone: value }); setMemberErrors({ ...memberErrors, phone: validateMemberForm({ ...memberForm, phone: value }).phone }); }} aria-invalid={Boolean(memberErrors.phone)} placeholder="(00) 00000-0000" />{memberErrors.phone && <small className="field-error">{memberErrors.phone}</small>}</label><button className="primary-button" disabled={memberSaving}>{memberSaving ? "Salvando..." : editingMemberId ? "Salvar alterações" : "Salvar membro"}</button></form>}<div className="data-table"><div className="table-header"><span>Nome</span><span>E-mail</span><span>Telefone</span><span>Status</span><span>Ações</span></div>{visibleMembers.length ? visibleMembers.map((member) => <div className="table-row member-row" key={member.id}><strong>{member.full_name}</strong><span>{member.email || "Não informado"}</span><span>{member.phone || "Não informado"}</span><span className="status-pill">Ativo</span><span className="row-actions"><button className="icon-button row-action" onClick={() => startEditingMember(member)} title="Editar membro" aria-label={`Editar ${member.full_name}`}><Pencil size={15} /></button><button className="icon-button row-action danger" onClick={() => removeMember(member)} title="Inativar membro" aria-label={`Inativar ${member.full_name}`}><Trash2 size={15} /></button></span></div>) : <div className="empty-state">Nenhum membro encontrado.</div>}</div></section>}
          {activeSection === "events" && <section className="section-view"><div className="section-heading"><div><p className="eyebrow warm">CALENDÁRIO</p><h2>Eventos e cultos</h2><p className="muted">Acompanhe os próximos encontros da comunidade.</p></div><button className="primary-button" onClick={() => setShowEventForm((open) => !open)}>{showEventForm ? "Fechar formulário" : "Novo evento"} <ArrowUpRight size={16} /></button></div>{showEventForm && <form className="inline-form event-form" onSubmit={createEvent}><label>Título<input required minLength="2" value={eventForm.title} onChange={(event) => setEventForm({ ...eventForm, title: event.target.value })} placeholder="Culto de domingo" /></label><label>Início<input required type="datetime-local" value={eventForm.starts_at} onChange={(event) => setEventForm({ ...eventForm, starts_at: event.target.value })} /></label><label>Fim<input type="datetime-local" value={eventForm.ends_at} onChange={(event) => setEventForm({ ...eventForm, ends_at: event.target.value })} /></label><label>Local<input value={eventForm.location} onChange={(event) => setEventForm({ ...eventForm, location: event.target.value })} placeholder="Templo principal" /></label><button className="primary-button" disabled={eventSaving}>{eventSaving ? "Salvando..." : "Salvar evento"}</button></form>}<div className="event-board">{events.length ? events.map((event) => <div className="event-card" key={event.id}><div className="event-date"><strong>{new Date(event.starts_at).getDate()}</strong><span>{new Intl.DateTimeFormat("pt-BR", { month: "long" }).format(new Date(event.starts_at))}</span></div><div><h3>{event.title}</h3><p>{event.location || "Local não informado"}</p><small>{formatDate(event.starts_at)}</small></div><div className="event-actions"><span className="status-pill">Agendado</span><button className="secondary-button" onClick={() => openAttendance(event.id)}>Presenças</button><button className="danger-button" onClick={() => cancelEvent(event.id)}>Cancelar</button></div></div>) : <div className="empty-state">Nenhum evento agendado.</div>}</div>{attendanceEventId && <div className="panel attendance-panel"><div className="panel-heading"><div><p className="eyebrow">PRESENÇAS</p><h3>Registrar presença</h3></div><button className="text-link" onClick={() => setAttendanceEventId(null)}>Fechar</button></div><form className="attendance-form" onSubmit={markMemberAttendance}><select required value={attendanceMemberId} onChange={(event) => setAttendanceMemberId(event.target.value)}><option value="">Selecione um membro</option>{members.map((member) => <option key={member.id} value={member.id}>{member.full_name}</option>)}</select><button className="primary-button">Marcar presente</button></form><div className="attendance-list">{attendance.length ? attendance.map((record) => <div key={record.member_id}><span>{record.full_name}</span><span className="status-pill">Presente</span></div>) : <p className="muted">Nenhuma presença registrada.</p>}</div></div>}</section>}
          {activeSection === "finance" && <section className="section-view">{canViewFinance ? <><div className="section-heading"><div><p className="eyebrow warm">GESTÃO</p><h2>Financeiro</h2><p className="muted">Movimentações da competência selecionada.</p></div><div className="section-actions"><label className="period-picker">Competência<input type="month" value={period} onChange={(event) => setPeriod(event.target.value)} /></label><button className="primary-button" onClick={() => setShowFinanceForm((open) => !open)}>{showFinanceForm ? "Fechar" : "Novo lançamento"} <ArrowUpRight size={16} /></button></div></div>{showFinanceForm && <form className="inline-form finance-form" onSubmit={createFinanceTransaction}><label>Tipo<select value={financeForm.kind} onChange={(event) => setFinanceForm({ ...financeForm, kind: event.target.value, category_id: "" })}><option value="income">Entrada</option><option value="expense">Saída</option></select></label><label>Conta<select required value={financeForm.account_id} onChange={(event) => setFinanceForm({ ...financeForm, account_id: event.target.value })}><option value="">Selecione</option>{financeAccounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label>Categoria<select required value={financeForm.category_id} onChange={(event) => setFinanceForm({ ...financeForm, category_id: event.target.value })}><option value="">Selecione</option>{financeCategories.filter((category) => category.kind === financeForm.kind).map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label>Valor<input required min="0.01" step="0.01" type="number" value={financeForm.amount} onChange={(event) => setFinanceForm({ ...financeForm, amount: event.target.value })} placeholder="0,00" /></label><label>Descrição<input required minLength="2" value={financeForm.description} onChange={(event) => setFinanceForm({ ...financeForm, description: event.target.value })} placeholder="Dízimo, aluguel..." /></label><label>Data<input required type="date" value={financeForm.occurred_on} onChange={(event) => setFinanceForm({ ...financeForm, occurred_on: event.target.value })} /></label><button className="primary-button" disabled={financeSaving}>{financeSaving ? "Salvando..." : "Registrar"}</button></form>}<div className="metric-grid compact"><article className={`metric-card featured ${summary?.net_cents < 0 ? "negative-card" : ""}`}><div className="metric-label">Resultado líquido</div><strong className={summary?.net_cents < 0 ? "negative-balance" : ""}>{formatMoney(summary?.net_cents)}</strong></article><article className="metric-card"><div className="metric-label">Entradas</div><strong>{formatMoney(summary?.income_cents)}</strong></article><article className="metric-card"><div className="metric-label">Saídas</div><strong>{formatMoney(summary?.expense_cents)}</strong></article></div><div className="panel transactions-panel"><div className="panel-heading"><div><p className="eyebrow">LANÇAMENTOS</p><h3>Últimas movimentações</h3></div></div><div className="data-table">{transactions.length ? transactions.map((transaction) => <div className="table-row transaction-row" key={transaction.id}><strong>{transaction.description}</strong><span>{transaction.occurred_on}</span><span className={transaction.kind === "income" ? "income-text" : "expense-text"}>{transaction.kind === "income" ? "+" : "-"}{formatMoney(transaction.amount_cents)}</span></div>) : <div className="empty-state">Nenhum lançamento nesta competência.</div>}</div></div></> : <div className="permission-state"><WalletCards size={27} /><h2>Financeiro restrito</h2><p>Somente proprietários e administradores podem consultar as movimentações da igreja.</p></div>}</section>}
        </section>
      </main>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("igreja_access_token"));
  async function logout() {
    if (token) await request("/api/v1/auth/logout", { method: "POST", headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
    localStorage.removeItem("igreja_access_token");
    setToken(null);
  }
  return token ? <Dashboard token={token} onLogout={logout} /> : <LoginScreen onLogin={setToken} />;
}