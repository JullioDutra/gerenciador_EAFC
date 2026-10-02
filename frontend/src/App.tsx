import { useEffect, useState } from "react";
import { Bell as BellIcon, BarChart3, Eye, CalendarDays, KeyRound, LayoutList, Lock, LogOut, Mail, Plus, Shield, Swords, Trophy, UserCircle2 } from "lucide-react";
import { api, getToken, setToken, useData } from "./api";
import { Admin, Bracket, CheckIn, CreateSeasonForm, Dashboard, Profile, Rounds, Standings, Stats } from "./pages";

// Importação da logo (agora lida a partir da pasta src/assets)
import logoEsports from "./assets/logoEsports.png";

const TABS = [
  { key: "Classificação", icon: LayoutList },
  { key: "Rodadas", icon: CalendarDays },
  { key: "Playoff", icon: Shield },
  { key: "Mata-mata", icon: Swords },
  { key: "Estatísticas", icon: BarChart3 },
  { key: "Meu campeonato", icon: Trophy },
  { key: "Meu perfil", icon: UserCircle2 },
  { key: "Admin", icon: Shield },
];

function Bell() {
  const { data, reload } = useData<any[]>("/notifications/");
  const [open, setOpen] = useState(false);
  const unread = data?.filter((n) => !n.read).length ?? 0;
  const openIt = async () => { setOpen((o) => !o); if (!open && unread) { await api("/notifications/read-all/", { method: "POST" }); reload(); } };
  return (
    <div className="relative">
      <button onClick={openIt} className="relative text-muted hover:text-ice p-2 rounded-lg hover:bg-panel2 transition-colors" aria-label="Notificações">
        <BellIcon size={20} />
        {unread > 0 && <span className="absolute top-1 right-1 bg-gold text-navy text-[10px] font-bold rounded-full w-4 h-4 flex items-center justify-center">{unread}</span>}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 card z-10 max-h-80 overflow-y-auto">
          {(!data || data.length === 0) && <p className="text-muted text-sm">Nenhuma notificação.</p>}
          {data?.map((n) => <p key={n.id} className="text-sm py-1.5 border-t border-line first:border-0 first:pt-0">{n.text}</p>)}
        </div>
      )}
    </div>
  );
}

function AdminLogin({ onDone }: { onDone: () => void }) {
  const [email, setEmail] = useState(""); const [pw, setPw] = useState(""); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try { 
      const r = await api("/auth/login/", { method: "POST", body: { username: email, password: pw } }); 
      setToken(r.token); 
      localStorage.setItem("is_admin", "true");
      onDone(); 
    }
    catch { setErr("E-mail ou senha incorretos."); } finally { setBusy(false); }
  };
  return (
    <div className="card space-y-3">
      <label className="block">
        <span className="sr-only">E-mail</span>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Mail size={17} className="text-muted" />
          </div>
          <input className="inp w-full" style={{ paddingLeft: "2.5rem" }} placeholder="E-mail" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && go()} />
        </div>
      </label>
      <label className="block">
        <span className="sr-only">Senha</span>
        <div className="relative">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Lock size={17} className="text-muted" />
          </div>
          <input className="inp w-full" style={{ paddingLeft: "2.5rem" }} type="password" placeholder="Senha" value={pw} onChange={(e) => setPw(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && go()} />
        </div>
      </label>
      {err && <p className="text-rose-300 text-sm">{err}</p>}
      <button className="btn w-full justify-center" onClick={go} disabled={busy}>{busy ? "Entrando…" : "Entrar"}</button>
    </div>
  );
}

function Entry({ sid, onDone }: { sid?: number; onDone: (sid?: number) => void }) {
  const [mode, setMode] = useState<"checkin" | "admin">("checkin");
  return (
    <div className="min-h-screen flex items-center justify-center p-4 relative overflow-hidden">
      <div className="blob absolute -top-24 -left-24 w-96 h-96 bg-royal/20 rounded-full blur-3xl" />
      <div className="blob absolute -bottom-24 -right-24 w-96 h-96 bg-teal/15 rounded-full blur-3xl" style={{ animationDelay: "3s" }} />
      <div className="w-full max-w-sm relative">
        <div className="flex flex-col items-center mb-6 text-center">
            <div className="w-16 h-16 rounded-2xl shadow-soft mb-4 overflow-hidden flex items-center justify-center">
              {/* Logo atualizada com a variável */}
              <img src={logoEsports} alt="5th E-Sports" className="w-full h-full object-contain" />
            </div>
          <p className="text-sm font-display font-bold text-teal tracking-[0.3em] uppercase">5th E-Sports</p>
          <h1 className="text-3xl">UniEVANGÉLICA</h1>
          <p className="text-muted text-sm mt-1">Faça seu check-in e entre no campeonato.</p>
        </div>
        {mode === "checkin" ? <CheckIn sid={sid} onDone={(token, s) => { setToken(token); onDone(s); }} /> : <AdminLogin onDone={() => onDone()} />}
        <button className="w-full text-center text-xs text-muted hover:text-ice mt-4 inline-flex items-center justify-center gap-1"
          onClick={() => setMode((m) => (m === "checkin" ? "admin" : "checkin"))}>
          <KeyRound size={12} />{mode === "checkin" ? "Sou organizador" : "Voltar para o check-in"}
        </button>
      </div>
    </div>
  );
}

export default function App() {
  const [authed, setAuthed] = useState(!!getToken());
  const isAdmin = localStorage.getItem("is_admin") === "true";
  const [tab, setTab] = useState(TABS[0].key);
  const [seasons, setSeasons] = useState<any[]>();
  const [sid, setSid] = useState<number>();
  const [creating, setCreating] = useState(false);
  const [mine, setMine] = useState<any[]>();  // campeonatos em que o jogador participa
  const [picked, setPicked] = useState(false);  // já escolheu em qual entrar (quando joga em mais de um)
  const choose = (id: number) => { setSid(id); setPicked(true); try { localStorage.setItem("sid", String(id)); } catch { /* sem storage */ } };
  const loadMine = () => api("/seasons/mine/").then((m: any[]) => {
    setMine(m);
    const saved = Number(localStorage.getItem("sid")); const ok = m.find((x) => x.id === saved);
    if (ok) { setSid(ok.id); setPicked(true); } else if (m.length === 1) { setSid(m[0].id); setPicked(true); }
  }).catch(() => setMine([]));
  const loadSeasons = () => api("/seasons/").then((s) => { setSeasons(s); setSid((cur) => cur ?? s.at(-1)?.id); })
    .catch(() => { setSeasons((cur) => cur ?? []); if (authed) { setToken(null); setAuthed(false); } });
  useEffect(() => { loadSeasons(); }, []);
  useEffect(() => { if (authed && !isAdmin) loadMine(); }, [authed]);
  if (seasons === undefined) return null;
  const fmt = seasons.find((s) => s.id === sid)?.config?.format ?? "league";
  const member = isAdmin || !!mine?.some((m) => m.id === sid);  // fora do campeonato só dá para visualizar
  const shownTabs = TABS.filter(({ key }) => !(key === "Playoff" && fmt !== "league") && !(key === "Classificação" && fmt === "knockout")
    && !((key === "Meu campeonato" || key === "Meu perfil") && !member));
  const curTab = shownTabs.some((t) => t.key === tab) ? tab : shownTabs[0].key;
  if (!authed) return <Entry sid={sid} onDone={(s) => { setAuthed(true); if (s) setSid(s); loadSeasons(); }} />;
  if (!isAdmin && mine === undefined) return null;
  if (!isAdmin && mine && mine.length > 1 && !picked) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="card w-full max-w-sm space-y-3">
          <h2 className="text-2xl font-bold">Em qual campeonato você quer entrar?</h2>
          <p className="text-sm text-muted">Você participa de mais de um. Dá para trocar depois, pelo seletor no topo.</p>
          {mine.map((s) => (
            <button key={s.id} className="btn w-full justify-center" onClick={() => choose(s.id)}>
              <Trophy size={16} />{s.name} {s.year}{s.jogo ? ` · ${s.jogo}` : ""}</button>))}
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-6xl mx-auto p-4">
      <header className="flex flex-wrap items-center gap-3 border-b border-line pb-4 mb-6">
        <div className="w-9 h-9 rounded-xl shrink-0 overflow-hidden flex items-center justify-center">
          {/* Logo atualizada com a variável */}
          <img src={logoEsports} alt="5th E-Sports" className="w-full h-full object-cover" />
        </div>
        <h1 className="text-xl font-bold mr-2">5th E-Sports</h1>
        {seasons.length > 0 && (
          <select className="inp !w-auto !py-1.5 text-sm" value={sid} onChange={(e) => { const id = Number(e.target.value); if (mine?.some((m) => m.id === id)) choose(id); else setSid(id); }}>
            {seasons.map((s) => <option key={s.id} value={s.id}>{s.name} {s.year}{!isAdmin && !mine?.some((m) => m.id === s.id) ? " (só visualização)" : ""}</option>)}
          </select>
        )}
        {isAdmin && <button className="text-muted hover:text-ice p-1.5 rounded-lg hover:bg-panel2 transition-colors" title="Nova temporada" onClick={() => setCreating((c) => !c)}>
          <Plus size={18} />
        </button>}
        <nav className="flex flex-wrap gap-1 flex-1">
          {shownTabs.map(({ key, icon: Icon }) => {
            if (key === "Admin" && !isAdmin) return null;
            return (
              <button key={key} onClick={() => setTab(key)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  curTab === key ? "bg-royal text-white" : "text-muted hover:text-ice hover:bg-panel2"}`}>
                <Icon size={16} />{key}
              </button>
            );
          })}
        </nav>
        <Bell />
        <button className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ice px-2 py-1.5 rounded-lg hover:bg-panel2 transition-colors"
          onClick={() => { setToken(null); localStorage.removeItem("is_admin"); localStorage.removeItem("sid"); setMine(undefined); setPicked(false); setAuthed(false); }}><LogOut size={16} />Sair</button>
      </header>
      {!member && sid && (
        <div className="mb-6 rounded-xl border border-line bg-panel2 px-4 py-2.5 text-sm text-muted flex items-center gap-2">
          <Eye size={16} className="text-gold" />
          {mine && mine.length > 0 ? "Modo visualização: você não participa deste campeonato." : "Você ainda não participa de nenhum campeonato; só dá para visualizar."}
          {mine?.[0] && <button className="text-teal hover:underline ml-auto" onClick={() => choose(mine[0].id)}>Voltar ao meu campeonato</button>}
        </div>
      )}
      {creating && isAdmin && (
        <div className="mb-6">
          <CreateSeasonForm onCreated={(id) => { setCreating(false); setSid(id); loadSeasons(); }} />
        </div>
      )}
      {!sid ? (
        !creating && <div className="space-y-3">
          <p className="text-muted">Nenhuma temporada criada ainda.</p>
          {isAdmin && <CreateSeasonForm onCreated={(id) => { setSid(id); loadSeasons(); }} />}
        </div>
      ) : <>
        {curTab === "Classificação" && <Standings sid={sid} />}
        {curTab === "Rodadas" && <Rounds sid={sid} />}
        {curTab === "Playoff" && <Bracket sid={sid} phases={["playoff1", "playoff2"]} />}
        {curTab === "Mata-mata" && <Bracket sid={sid} phases={["r32", "r16", "qf", "sf", "final"]} showChampion />}
        {curTab === "Estatísticas" && <Stats sid={sid} />}
        {curTab === "Meu campeonato" && <Dashboard sid={sid} />}
        {curTab === "Meu perfil" && <Profile sid={sid} />}
        {curTab === "Admin" && isAdmin && <Admin sid={sid} />}
      </>}
    </div>
  );
}
