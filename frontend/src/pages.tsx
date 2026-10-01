import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle, BarChart3, CalendarDays, CheckCircle2, Clock, Filter, FlagTriangleRight, Flame, Goal,
  ListOrdered, Scale, Settings2, Shield, ShieldAlert, Sparkles, Swords, Target, Trophy, Upload, UserCircle2, Users,
} from "lucide-react";
import { api, useData } from "./api";

const ZONE: Record<string, string> = { direct: "border-l-teal", playoff: "border-l-gold", out: "border-l-rose-400/70" };
const LABEL: Record<string, string> = { pending: "Pendente", awaiting: "Aguardando confirmação", confirmed: "Confirmado",
  disputed: "Contestação aberta", resolved: "Resolvido pelo admin", wo: "WO" };
const DONE = ["confirmed", "resolved", "wo"];
const STATUS_META: Record<string, { icon: any; chip: string }> = {
  pending: { icon: Clock, chip: "chip-muted" }, awaiting: { icon: Clock, chip: "chip-muted" },
  confirmed: { icon: CheckCircle2, chip: "chip-teal" }, resolved: { icon: CheckCircle2, chip: "chip-teal" },
  wo: { icon: FlagTriangleRight, chip: "chip-gold" }, disputed: { icon: AlertTriangle, chip: "chip-rose" },
};
function StatusChip({ status }: { status: string }) {
  const m = STATUS_META[status] ?? STATUS_META.pending; const Icon = m.icon;
  return <span className={m.chip}><Icon size={12} />{LABEL[status]}</span>;
}
function SectionTitle({ icon: Icon, children }: { icon: any; children: ReactNode }) {
  return <h3 className="text-xl font-bold flex items-center gap-2"><Icon size={19} className="text-royal" />{children}</h3>;
}

function useNames(sid: number) {
  const { data } = useData<any[]>(`/seasons/${sid}/standings/`);
  const names: Record<number, string> = {}; data?.forEach((r) => (names[r.player.id] = r.player.nickname + (r.player.team ? ` (${r.player.team})` : "")));
  return { rows: data, n: (id: number | null) => (id ? names[id] ?? `#${id}` : "Folga") };
}
const score = (m: any) => (m.score_a === null ? "—" : `${m.score_a} x ${m.score_b}${m.pen_a != null ? ` (${m.pen_a}-${m.pen_b} pên.)` : ""}`);
const Err = ({ e }: { e: string }) => (e ? <p className="text-red-400 text-sm">{e}</p> : null);

export function Standings({ sid }: { sid: number }) {
  const { rows } = useNames(sid);
  const th = "px-2 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted";
  return (
    <div className="card overflow-x-auto space-y-3">
      <SectionTitle icon={ListOrdered}>Classificação</SectionTitle>
      <table className="w-full text-sm">
        <thead><tr><th className={th}>Pos</th><th className={th + " text-left"}>Jogador</th>
          {["J", "V", "E", "D", "GP", "GC", "SG", "Pts"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
        <tbody>{rows?.map((r) => (
          <tr key={r.player.id} className={`border-l-2 border-t border-t-line ${ZONE[r.zone]}`}>
            <td className="px-2 py-1.5 text-right text-muted">{r.pos}</td>
            <td className="px-2 py-1.5 font-medium">{r.player.nickname}{r.player.team && <span className="text-muted font-normal"> ({r.player.team})</span>}</td>
            {[r.j, r.v, r.e, r.d, r.gp, r.gc, r.sg].map((v, i) => <td key={i} className="px-2 text-right text-muted">{v}</td>)}
            <td className="px-2 text-right font-bold text-gold">{r.pts}</td>
          </tr>))}</tbody>
      </table>
      <div className="flex flex-wrap gap-3 text-xs text-muted pt-1">
        <span className="chip-teal">Classificação direta</span><span className="chip-gold">Playoff</span><span className="chip-rose">Eliminado</span>
      </div>
    </div>
  );
}

const FORMAT_LABEL: Record<string, string> = { single: "Partida única", bo3: "Melhor de 3", bo5: "Melhor de 5", two_legs: "Ida e volta" };
const legScore = (l: any) => (l.score_a === null ? "—" : `${l.score_a}-${l.score_b}${l.pen_a != null ? ` (${l.pen_a}-${l.pen_b} pên.)` : ""}${l.extra_time ? " pró." : ""}`);

function MatchRow({ m, n }: { m: any; n: (i: number | null) => string }) {
  const multi = m.match_format && m.match_format !== "single";
  return (
    <div className="py-2.5 border-t border-line text-sm">
      <div className="grid grid-cols-[2rem_1fr_auto_1fr_auto] gap-3 items-center">
        <span className="text-muted text-xs">{String(m.slot).padStart(3, "0")}</span>
        <span className="text-right font-medium">{n(m.player_a)}</span>
        <span className="font-display text-lg font-bold text-gold px-2">{score(m)}{m.extra_time && " pró."}</span>
        <span className="font-medium">{n(m.player_b)}</span>
        <StatusChip status={m.status} />
      </div>
      {multi && m.legs?.length > 0 && (
        <p className="text-xs text-muted text-right mt-1">{FORMAT_LABEL[m.match_format]} · {m.legs.map((l: any) => `Jogo ${l.number}: ${legScore(l)}`).join(" · ")}</p>
      )}
    </div>
  );
}

function ExtraTimeTimer() {
  const [secs, setSecs] = useState(600); const [running, setRunning] = useState(false);
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setSecs((s) => (s > 0 ? s - 1 : 0)), 1000);
    return () => clearInterval(id);
  }, [running]);
  const mm = String(Math.floor(secs / 60)).padStart(2, "0"); const ss = String(secs % 60).padStart(2, "0");
  return (
    <div className="flex items-center gap-2 text-sm bg-navy border border-line rounded-lg px-2.5 py-1.5">
      <Clock size={15} className="text-gold" />
      <span className="font-display text-lg font-bold tabular-nums">{mm}:{ss}</span>
      <button type="button" className="text-muted hover:text-ice text-xs font-medium" onClick={() => setRunning((r) => !r)}>{running ? "Pausar" : "Iniciar"}</button>
      <button type="button" className="text-muted hover:text-ice text-xs font-medium" onClick={() => { setRunning(false); setSecs(600); }}>Zerar</button>
    </div>
  );
}

/** Formulário genérico de placar, usado para partida única e para cada jogo de um confronto de ida-e-volta/melhor-de-X. */
function ReportForm({ labelA, labelB, onSubmit }: { labelA: string; labelB: string; onSubmit: (f: FormData) => Promise<void> }) {
  const [a, setA] = useState(""); const [b, setB] = useState(""); const [pa, setPa] = useState(""); const [pb, setPb] = useState("");
  const [et, setEt] = useState(false); const [proof, setProof] = useState<File>(); const [e, setE] = useState("");
  const tied = a !== "" && b !== "" && Number(a) === Number(b);
  const send = async () => {
    try {
      const f = new FormData(); f.append("score_a", a); f.append("score_b", b); f.append("et", String(et));
      if (pa) f.append("pen_a", pa); if (pb) f.append("pen_b", pb); if (proof) f.append("proof", proof);
      await onSubmit(f); setE("");
    } catch (x: any) { setE(x.message); }
  };
  return (
    <div className="space-y-2">
      <p className="text-sm">Informe o placar ({labelA} x {labelB}). O adversário confirma enviando o mesmo placar.</p>
      <div className="flex flex-wrap gap-2 items-center">
        <input className="inp !w-20" type="number" min={0} value={a} onChange={(x) => setA(x.target.value)} />
        <input className="inp !w-20" type="number" min={0} value={b} onChange={(x) => setB(x.target.value)} />
        <label className="text-xs text-muted inline-flex items-center gap-1 cursor-pointer">
          <Upload size={14} />Comprovante
          <input type="file" accept="image/*" className="hidden" onChange={(x) => setProof(x.target.files?.[0])} />
          {proof && <span className="text-teal">✓</span>}
        </label>
        <button className="btn" onClick={send}>Enviar resultado</button>
      </div>
      {tied && (
        <div className="flex flex-wrap gap-3 items-center bg-panel2 border border-line rounded-lg p-2.5">
          <label className="text-sm flex items-center gap-1.5"><input type="checkbox" checked={et} onChange={(x) => setEt(x.target.checked)} /> Foi à prorrogação</label>
          {et && <ExtraTimeTimer />}
          <span className="text-sm text-muted">Pênaltis (se houve):</span>
          <input className="inp !w-16" type="number" min={0} placeholder={labelA} value={pa} onChange={(x) => setPa(x.target.value)} />
          <input className="inp !w-16" type="number" min={0} placeholder={labelB} value={pb} onChange={(x) => setPb(x.target.value)} />
        </div>
      )}
      <Err e={e} />
    </div>
  );
}

export function Rounds({ sid }: { sid: number }) {
  const { n } = useNames(sid);
  const { data: rounds } = useData<any[]>(`/rounds/?season=${sid}`);
  const [rid, setRid] = useState<number>(); const [f, setF] = useState("all");
  const cur = rid ?? rounds?.at(-1)?.id;
  const { data: ms } = useData<any[]>(cur ? `/matches/?round=${cur}` : null);
  const shown = ms?.filter((m) => f === "all" || (f === "pending" && !DONE.includes(m.status) && m.status !== "disputed") ||
    (f === "done" && DONE.includes(m.status)) || (f === "disputed" && m.status === "disputed"));
  const FILTERS: [string, string, any][] = [["all", "Todos", Filter], ["pending", "Pendentes", Clock], ["done", "Finalizados", CheckCircle2], ["disputed", "Disputas", AlertTriangle]];
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-1.5">{rounds?.map((r) => (
        <button key={r.id} onClick={() => setRid(r.id)} className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${cur === r.id ? "bg-royal text-white" : "bg-panel2 border border-line text-muted hover:text-ice"}`}>{r.name}</button>))}</div>
      <div className="flex gap-1.5">{FILTERS.map(([k, t, Icon]) => (
        <button key={k} onClick={() => setF(k)} className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-lg text-sm font-medium transition-colors ${f === k ? "bg-gold text-navy" : "bg-panel2 border border-line text-muted hover:text-ice"}`}><Icon size={14} />{t}</button>))}</div>
      <div className="card">{shown?.map((m) => <MatchRow key={m.id} m={m} n={n} />)}{shown?.length === 0 && <p className="text-muted">Nenhuma partida neste filtro.</p>}</div>
    </div>
  );
}

const SLOT = 64; const CARD = 48; const GUTTER = 32;

export function Bracket({ sid, phases, showChampion }: { sid: number; phases: string[]; showChampion?: boolean }) {
  const { n } = useNames(sid);
  const { data: rounds } = useData<any[]>(`/rounds/?season=${sid}`);
  const { data: matches } = useData<any[]>(`/matches/?season=${sid}`);
  const { data: season } = useData<any>(`/seasons/${sid}/`);
  const cols = rounds?.filter((r) => phases.includes(r.phase)) ?? [];
  const ready = cols.length > 0 && matches;
  return (
    <div className="space-y-4">
      {showChampion && season?.champion && (
        <div className="champion rounded-2xl p-8 text-center border border-gold/30 flex flex-col items-center gap-2">
          <Trophy size={36} className="text-gold" />
          <h2 className="text-3xl font-bold">Campeão: <span className="text-gold">{n(season.champion)}</span></h2>
        </div>)}
      {cols.length === 0 && <p className="text-muted">Esta fase começa quando a anterior terminar.</p>}
      {ready && <BracketBody cols={cols} matches={matches!} n={n} />}
    </div>
  );
}

function BracketBody({ cols, matches, n }: { cols: any[]; matches: any[]; n: (i: number | null) => string }) {
  const data = cols.map((r) => matches.filter((m) => m.round === r.id).sort((a, b) => a.slot - b.slot));
  if (data[0]?.length === 0) return null;
  const leaves = data[0].length;
  const H = leaves * SLOT;
  const centerY = (i: number, N: number) => ((i + 0.5) / N) * H;
  return (
    <div className="flex overflow-x-auto pb-2">
      {cols.map((r, ci) => {
        const ms = data[ci]; const N = ms.length || 1;
        return (
          <div key={r.id} className="flex">
            <div style={{ height: H }} className="relative" >
              <h3 className="text-sm font-bold text-muted uppercase tracking-wide absolute -top-7 left-0 whitespace-nowrap">{r.name}</h3>
              {ms.map((m, i) => (
                <div key={m.id} style={{ position: "absolute", top: centerY(i, N) - CARD / 2, height: CARD, width: 220 }}
                  className="card !p-1.5 text-xs flex flex-col justify-center gap-0.5">
                  {[["player_a", "score_a"], ["player_b", "score_b"]].map(([p, s]) => (
                    <div key={p} className={`flex justify-between ${m.winner && m.winner === m[p] ? "text-gold font-bold" : ""}`}>
                      <span className="truncate">{n(m[p])}</span><span>{m[s] ?? "–"}</span></div>))}
                </div>))}
            </div>
            {ci < cols.length - 1 && (
              <div style={{ height: H, width: GUTTER }} className="relative shrink-0">
                {Array.from({ length: N / 2 }).map((_, k) => {
                  const top = centerY(2 * k, N), bot = centerY(2 * k + 1, N), mid = (top + bot) / 2;
                  return (
                    <div key={k}>
                      <div style={{ position: "absolute", left: 0, width: "50%", top, height: bot - top }}
                        className="border-t-2 border-b-2 border-r-2 border-line" />
                      <div style={{ position: "absolute", left: "50%", width: "50%", top: mid }} className="border-t-2 border-line" />
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

const STAT_LABELS: Record<string, string> = { most_wins: "Mais vitórias", most_goals: "Mais gols marcados",
  best_diff: "Melhor saldo", most_played: "Mais partidas disputadas", longest_win_streak: "Maior sequência de vitórias",
  longest_unbeaten: "Maior sequência invicta", best_campaign: "Melhor campanha" };

const STAT_ICONS: Record<string, any> = { most_wins: Trophy, most_goals: Goal, best_diff: Scale, most_played: CalendarDays,
  longest_win_streak: Flame, longest_unbeaten: Shield, best_campaign: Sparkles };

export function Stats({ sid }: { sid: number }) {
  const { data } = useData<any>(`/seasons/${sid}/stats/`);
  if (!data) return null;
  return (
    <div className="space-y-4">
      <SectionTitle icon={BarChart3}>Estatísticas do campeonato</SectionTitle>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[["Partidas disputadas", data.total_matches, Swords], ["Gols marcados", data.total_goals, Goal], ["Média de gols/partida", data.avg_goals_per_match, Target]].map(([t, v, Icon]: any) => (
          <div key={t} className="card text-center space-y-1"><Icon size={20} className="text-royal mx-auto" /><div className="font-display text-3xl font-extrabold">{v}</div><div className="text-xs text-muted">{t}</div></div>))}
      </div>
      <div className="grid md:grid-cols-2 gap-3">
        {Object.entries(STAT_LABELS).map(([k, label]) => { const r = data[k]; if (!r) return null; const Icon = STAT_ICONS[k];
          const val = k === "most_wins" ? r.wins : k === "most_goals" ? r.goals : k === "best_diff" ? r.goals :
            k === "most_played" ? r.played : k === "longest_win_streak" ? r.best_streak : k === "longest_unbeaten" ? r.unbeaten : r.deepest;
          return (
            <div key={k} className="card flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-panel2 flex items-center justify-center shrink-0"><Icon size={18} className="text-gold" /></div>
              <div className="flex-1"><div className="text-xs text-muted">{label}</div><div className="font-display font-bold">{r.player.nickname}</div></div>
              <div className="text-2xl font-display font-extrabold text-gold">{val}</div>
            </div>);
        })}
      </div>
    </div>
  );
}

export function Dashboard({ sid }: { sid: number }) {
  const { data: me, err, reload } = useData<any>(`/seasons/${sid}/me/`);
  const { n } = useNames(sid);
  if (err) return <p className="text-muted">Você não está inscrito nesta temporada.</p>;
  if (!me) return null;
  const nm = me.next_match;
  const multi = nm && nm.match_format && nm.match_format !== "single";
  const legsDone = nm?.legs?.filter((l: any) => DONE.includes(l.status)) ?? [];
  const nextLeg = legsDone.length + 1;
  const stat = (t: string, v: any) => <div className="card text-center"><div className="font-display text-3xl font-extrabold text-gold">{v}</div><div className="text-xs text-muted mt-0.5">{t}</div></div>;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-panel2 flex items-center justify-center shrink-0"><Trophy size={22} className="text-gold" /></div>
        <div>
          <h2 className="text-2xl font-bold">Você está em {me.position}º lugar</h2>
          {(me.player.team || me.player.campus) && <p className="text-sm text-muted">{me.player.team}{me.player.team && me.player.campus && " · "}{me.player.campus}</p>}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stat("Pontos", me.points)}{stat("V-E-D", me.record.join("-"))}{stat("Gols marcados", me.gf)}{stat("Saldo", me.gd)}</div>
      <div className="card space-y-2">
        <SectionTitle icon={Swords}>Próxima partida</SectionTitle>
        {nm ? <>
          <p>Adversário: <b>{n(nm.player_a === me.player.id ? nm.player_b : nm.player_a)}</b>{multi && <span className="text-muted text-sm"> · {FORMAT_LABEL[nm.match_format]}</span>}</p>
          <p className="text-sm text-muted flex items-center gap-1.5"><CalendarDays size={14} />{nm.deadline ? new Date(nm.deadline).toLocaleString("pt-BR") : "sem prazo"} <StatusChip status={nm.status} /></p>
          {multi && nm.legs?.length > 0 && (
            <ul className="text-sm text-muted">{nm.legs.map((l: any) => <li key={l.number}>Jogo {l.number}: {legScore(l)}</li>)}</ul>)}
          <ReportForm labelA={n(nm.player_a)} labelB={n(nm.player_b)} onSubmit={async (f) => {
            if (multi) f.append("leg_number", String(nextLeg));
            await api(`/matches/${nm.id}/${multi ? "report-leg" : "report"}/`, { method: "POST", form: f }); reload();
          }} />
        </> : <p className="text-muted">Nenhuma partida pendente.</p>}
      </div>
      <div className="card"><SectionTitle icon={ListOrdered}>Histórico</SectionTitle>
        {me.history.length === 0 && <p className="text-muted text-sm mt-2">Nenhuma partida disputada ainda.</p>}
        {me.history.map((m: any) => <MatchRow key={m.id} m={m} n={n} />)}</div>
    </div>
  );
}

export function Profile({ sid }: { sid: number }) {
  const { data: me, err, reload } = useData<any>(`/seasons/${sid}/me/`);
  const [f, setF] = useState<Record<string, string>>({}); const [avatarFile, setAvatarFile] = useState<File>(); const [msg, setMsg] = useState("");
  useEffect(() => { if (me) setF({ name: me.player.name, nickname: me.player.nickname, ea_id: me.player.ea_id,
    platform: me.player.platform, country: me.player.country, avatar: me.player.avatar }); }, [me?.player.id]);
  if (err) return <p className="text-muted">Você não está inscrito nesta temporada.</p>;
  if (!me) return null;
  const preview = avatarFile ? URL.createObjectURL(avatarFile) : me.player.avatar_url;
  const save = async () => {
    try {
      const form = new FormData(); Object.entries(f).forEach(([k, v]) => form.append(k, v ?? ""));
      if (avatarFile) form.append("avatar_file", avatarFile);
      await api(`/players/${me.player.id}/profile/`, { method: "PATCH", form }); setMsg("Perfil atualizado."); setAvatarFile(undefined); reload();
    } catch (x: any) { setMsg(x.message); }
  };
  const field = (key: string, label: string, placeholder = "") => (
    <label className="text-sm block"><span className="text-muted">{label}</span>
      <input className="inp mt-1" value={f[key] ?? ""} placeholder={placeholder} onChange={(e) => setF({ ...f, [key]: e.target.value })} /></label>);
  return (
    <div className="card max-w-lg space-y-4">
      <div className="flex items-center gap-4">
        <label className="relative cursor-pointer group shrink-0">
          {preview ? <img src={preview} alt="Avatar" className="w-16 h-16 rounded-2xl object-cover border-2 border-royal/40" />
            : <div className="w-16 h-16 rounded-2xl bg-panel2 border border-line flex items-center justify-center"><UserCircle2 size={30} className="text-muted" /></div>}
          <div className="absolute inset-0 bg-navy/60 opacity-0 group-hover:opacity-100 rounded-2xl flex items-center justify-center transition-opacity">
            <Upload size={18} /></div>
          <input type="file" accept="image/*" className="hidden" onChange={(e) => setAvatarFile(e.target.files?.[0])} />
        </label>
        <div>
          <h2 className="text-2xl font-bold">Meu perfil</h2>
          <p className="text-sm text-muted">Como os outros jogadores te veem na liga</p>
          {(me.player.team || me.player.campus) && <p className="text-xs text-teal mt-0.5">{me.player.team}{me.player.team && me.player.campus && " · "}{me.player.campus}</p>}
        </div>
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        {field("nickname", "Nickname")}
        {field("name", "Nome completo")}
        {field("ea_id", "EA ID")}
        {field("platform", "Plataforma", "PS5, Xbox Series, PC…")}
        {field("country", "País (código de 2 letras)", "BR")}
        {field("avatar", "URL do avatar (se não enviar foto)", "https://…")}
      </div>
      <div className="flex items-center gap-3">
        <button className="btn" onClick={save}>Salvar</button>
        <span className="text-sm text-teal">{msg}</span>
      </div>
    </div>
  );
}

/** Check-in do jogador: só o telefone, sem formulário. Busca a pré-inscrição e já loga. */
export function CheckIn({ sid, onDone }: { sid?: number; onDone: (token: string) => void }) {
  const [phone, setPhone] = useState(""); const [reg, setReg] = useState<any>(); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const lookup = async () => {
    setBusy(true); setErr("");
    try { setReg(await api("/checkin/lookup/", { method: "POST", body: { phone } })); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const confirm = async () => {
    if (!sid) { setErr("Nenhum campeonato disponível para check-in ainda."); return; }
    setBusy(true); setErr("");
    try { const r = await api("/checkin/confirm/", { method: "POST", body: { phone, season: sid } }); onDone(r.token); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (reg) {
    return (
      <div className="card space-y-3">
        <p className="text-sm text-muted">Encontramos sua inscrição:</p>
        <div className="bg-panel2 rounded-xl p-3 space-y-1">
          <p className="font-display text-xl font-bold">{reg.nome}</p>
          <p className="text-sm text-muted">{reg.equipe && <>Time: <span className="text-ice">{reg.equipe}</span> · </>}{reg.campus}</p>
          {reg.curso && <p className="text-xs text-muted">{reg.curso}</p>}
        </div>
        {reg.already_checked_in && <p className="text-xs text-gold flex items-center gap-1"><CheckCircle2 size={13} />Você já fez check-in antes — confirmar de novo só entra na sua conta.</p>}
        <Err e={err} />
        <div className="flex gap-2">
          <button className="btn-soft btn flex-1 justify-center" onClick={() => setReg(undefined)}>Não sou eu</button>
          <button className="btn flex-1 justify-center" onClick={confirm} disabled={busy}>{busy ? "Entrando…" : "Confirmar check-in"}</button>
        </div>
      </div>
    );
  }
  return (
    <div className="card space-y-3">
      <label className="block">
        <span className="text-sm text-muted">Telefone usado na inscrição</span>
        <input className="inp mt-1" placeholder="(62) 99999-9999" value={phone} onChange={(e) => setPhone(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && lookup()} />
      </label>
      <Err e={err} />
      <button className="btn w-full justify-center" onClick={lookup} disabled={busy || !phone}>{busy ? "Procurando…" : "Buscar minha inscrição"}</button>
    </div>
  );
}

export function CreateSeasonForm({ onCreated }: { onCreated: (id: number) => void }) {
  const thisYear = new Date().getFullYear();
  const [f, setF] = useState({ name: "Temporada", year: String(thisYear), swiss_rounds: "8", direct: "16", playoff_size: "48", playoff_qualify: "16" });
  const [msg, setMsg] = useState("");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const total = Number(f.direct || 0) + Number(f.playoff_size || 0);
  const create = async () => {
    try {
      const s = await api("/seasons/", { method: "POST", body: {
        name: f.name, year: Number(f.year),
        config: { swiss_rounds: Number(f.swiss_rounds), direct: Number(f.direct), playoff_size: Number(f.playoff_size), playoff_qualify: Number(f.playoff_qualify) },
      } });
      onCreated(s.id);
    } catch (x: any) { setMsg(x.message); }
  };
  const field = (k: string, label: string, w = "w-24") => (
    <label className="text-sm block"><span className="text-muted">{label}</span>
      <input className={`inp mt-1 ${w}`} type="number" min={0} value={(f as any)[k]} onChange={(e) => set(k, e.target.value)} /></label>);
  return (
    <div className="card max-w-xl space-y-4">
      <SectionTitle icon={Trophy}>Criar temporada</SectionTitle>
      <div className="grid sm:grid-cols-2 gap-3">
        <label className="text-sm block"><span className="text-muted">Nome</span>
          <input className="inp mt-1" value={f.name} onChange={(e) => set("name", e.target.value)} /></label>
        <label className="text-sm block"><span className="text-muted">Ano</span>
          <input className="inp mt-1" type="number" value={f.year} onChange={(e) => set("year", e.target.value)} /></label>
      </div>
      <div className="flex flex-wrap gap-3">
        {field("swiss_rounds", "Rodadas da fase de liga")}
        {field("direct", "Classificam direto")}
        {field("playoff_size", "Vão para o playoff")}
        {field("playoff_qualify", "Classificados do playoff")}
      </div>
      <p className="text-xs text-muted">
        Some quantos jogadores vão participar da fase de liga (o total é definido por quantos você cadastrar ou importar depois — não há limite fixo aqui).
        Com os valores acima: os {f.direct} melhores vão direto para a fase principal, os próximos {f.playoff_size} disputam o playoff
        (do qual saem {f.playoff_qualify} classificados) e o restante é eliminado. Para isso fechar, sua fase de liga deve ter pelo menos {total || 0} jogadores.
      </p>
      <div className="flex items-center gap-3">
        <button className="btn" onClick={create}>Criar temporada</button>
        <span className="text-sm text-rose-300">{msg}</span>
      </div>
      <p className="text-xs text-muted">Depois de criada, esses números continuam editáveis em Admin → Regras da temporada, e você importa os jogadores por CSV também em Admin.</p>
    </div>
  );
}

const TIEBREAK_OPTIONS: Record<string, string> = { pts: "Pontos", gd: "Saldo de gols", gf: "Gols marcados",
  wins: "Vitórias", ga: "Gols sofridos (menos é melhor)", buchholz: "Buchholz (força dos adversários)" };
const PLAYER_STATUS: Record<string, string> = { active: "Ativo", playoff: "Playoff", main: "Fase principal",
  eliminated: "Eliminado", blocked: "Bloqueado", champion: "Campeão" };

function RulesPanel({ sid }: { sid: number }) {
  const { data: season, reload } = useData<any>(`/seasons/${sid}/`);
  const [msg, setMsg] = useState("");
  if (!season) return null;
  const cfg = season.config ?? {};
  const tb: string[] = cfg.tiebreakers ?? ["pts", "gd", "gf", "wins"];
  const save = async (patch: object) => {
    try { await api(`/seasons/${sid}/`, { method: "PATCH", body: { config: { ...cfg, ...patch } } }); setMsg("Regras salvas."); reload(); }
    catch (x: any) { setMsg(x.message); }
  };
  const move = (i: number, dir: -1 | 1) => { const t = [...tb]; const j = i + dir; if (j < 0 || j >= t.length) return;
    [t[i], t[j]] = [t[j], t[i]]; save({ tiebreakers: t }); };
  const field = (key: string, label: string, w = "w-20") => (
    <label className="text-sm flex items-center gap-2">{label}
      <input className={`inp ${w}`} defaultValue={cfg[key] ?? ""} onBlur={(e) => save({ [key]: Number(e.target.value) })} /></label>);
  return (
    <div className="card space-y-3">
      <SectionTitle icon={Settings2}>Regras da temporada</SectionTitle>
      <div className="flex flex-wrap gap-4">
        {field("swiss_rounds", "Rodadas Swiss")}{field("direct", "Classificação direta")}
        {field("playoff_size", "Tamanho do playoff")}{field("playoff_qualify", "Classificados do playoff")}
        {field("round_days", "Dias por rodada")}
      </div>
      <div className="flex flex-wrap gap-4">
        {field("win", "Pontos por vitória", "w-14")}{field("draw", "Pontos por empate", "w-14")}{field("loss", "Pontos por derrota", "w-14")}
      </div>
      <div>
        <p className="text-sm text-muted mb-1">Critérios de desempate, em ordem de prioridade</p>
        <ol className="space-y-1">{tb.map((k, i) => (
          <li key={k} className="flex items-center gap-2 text-sm bg-panel2 rounded-lg px-2.5 py-1.5">
            <span className="w-5 text-muted">{i + 1}.</span><span className="flex-1">{TIEBREAK_OPTIONS[k] ?? k}</span>
            <button className="text-muted hover:text-ice disabled:opacity-30" onClick={() => move(i, -1)} disabled={i === 0}>↑</button>
            <button className="text-muted hover:text-ice disabled:opacity-30" onClick={() => move(i, 1)} disabled={i === tb.length - 1}>↓</button>
          </li>))}</ol>
      </div>
      <span className="text-sm text-teal">{msg}</span>
    </div>
  );
}

function PlayersPanel({ sid }: { sid: number }) {
  const { data: players, reload } = useData<any[]>(`/players/?season=${sid}`);
  const [msg, setMsg] = useState(""); const [pen, setPen] = useState<Record<number, string>>({}); const [reason, setReason] = useState<Record<number, string>>({});
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); setMsg(ok); reload(); } catch (x: any) { setMsg(x.message); } };
  return (
    <div className="card space-y-2">
      <SectionTitle icon={Users}>Jogadores</SectionTitle>
      <span className="text-sm text-teal">{msg}</span>
      <div className="max-h-96 overflow-y-auto space-y-1">
        {players?.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center gap-2 py-1.5 border-t border-line text-sm">
            <span className="flex-1 font-medium">{p.nickname}</span>
            <select className="inp !w-40 !py-1" value={p.status} onChange={(e) => run(() => api(`/players/${p.id}/`, { method: "PATCH", body: { status: e.target.value } }), "Status atualizado.")}>
              {Object.entries(PLAYER_STATUS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
            <input className="inp !w-16 !py-1" type="number" placeholder="pts" value={pen[p.id] ?? ""} onChange={(e) => setPen({ ...pen, [p.id]: e.target.value })} />
            <input className="inp !w-32 !py-1" placeholder="motivo" value={reason[p.id] ?? ""} onChange={(e) => setReason({ ...reason, [p.id]: e.target.value })} />
            <button className="btn !py-1 !px-2" onClick={() => run(() => api(`/players/${p.id}/penalty/`, { method: "POST", body: { points: pen[p.id] || 0, reason: reason[p.id] || "" } }), "Ajuste de pontos aplicado.")}>Aplicar</button>
          </div>))}
      </div>
      <p className="text-xs text-muted">Pontos positivos somam (bônus), negativos subtraem (punição). Status "Bloqueado" tira o jogador das próximas rodadas Swiss.</p>
    </div>
  );
}

function DeadlinesPanel({ sid }: { sid: number }) {
  const { data: rounds, reload } = useData<any[]>(`/rounds/?season=${sid}`);
  const [msg, setMsg] = useState("");
  const save = async (id: number, patch: object, ok: string) => {
    try { await api(`/rounds/${id}/`, { method: "PATCH", body: patch }); setMsg(ok); reload(); }
    catch (x: any) { setMsg(x.message); }
  };
  return (
    <div className="card space-y-2">
      <SectionTitle icon={CalendarDays}>Prazos e formato das rodadas</SectionTitle>
      <span className="text-sm text-teal">{msg}</span>
      {rounds?.map((r) => (
        <div key={r.id} className="flex flex-wrap items-center gap-2 py-1.5 border-t border-line text-sm">
          <span className="flex-1">{r.name}</span>
          <select className="inp !w-40 !py-1" value={r.match_format} onChange={(e) => save(r.id, { match_format: e.target.value }, "Formato atualizado.")}>
            {Object.entries(FORMAT_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <input className="inp !w-56 !py-1" type="datetime-local" defaultValue={r.deadline?.slice(0, 16)} onBlur={(e) => e.target.value && save(r.id, { deadline: new Date(e.target.value).toISOString() }, "Prazo atualizado.")} />
        </div>))}
      <p className="text-xs text-muted">Mudar o formato só afeta jogos ainda não iniciados nesta rodada.</p>
    </div>
  );
}

function DisputesPanel({ sid, n }: { sid: number; n: (i: number | null) => string }) {
  const { data: disputes, reload } = useData<any[]>(`/disputes/?season=${sid}&resolved=false`);
  const { data: matches } = useData<any[]>(`/matches/?season=${sid}`);
  const [msg, setMsg] = useState(""); const [sc, setSc] = useState<Record<string, string[]>>({});
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); setMsg(ok); reload(); } catch (x: any) { setMsg(x.message); } };
  const byId: Record<number, any> = {}; matches?.forEach((m) => (byId[m.id] = m));
  return (
    <div className="card space-y-2">
      <SectionTitle icon={ShieldAlert}>Disputas abertas</SectionTitle>
      <span className="text-sm text-teal">{msg}</span>
      {disputes?.length === 0 && <p className="text-muted flex items-center gap-1.5 text-sm"><CheckCircle2 size={15} className="text-teal" />Nenhuma disputa aberta.</p>}
      {disputes?.map((d) => {
        const m = byId[d.match]; if (!m) return null;
        const key = `${d.match}:${d.leg_number ?? "m"}`; const v = sc[key] ?? ["", ""];
        const setV = (i: number, val: string) => setSc({ ...sc, [key]: i ? [v[0], val] : [val, v[1]] });
        const resolve = () => d.leg_number
          ? api(`/matches/${d.match}/set-leg-result/`, { method: "POST", body: { leg_number: d.leg_number, score_a: v[0], score_b: v[1] } })
          : api(`/matches/${d.match}/set-result/`, { method: "POST", body: { score_a: v[0], score_b: v[1] } });
        return (
          <div key={d.id} className="flex flex-wrap items-center gap-2 py-2 border-t border-line text-sm">
            <span className="flex-1">{n(m.player_a)} x {n(m.player_b)}{d.leg_number ? ` · Jogo ${d.leg_number}` : ""}</span>
            {[0, 1].map((i) => <input key={i} className="inp !w-16" type="number" min={0} value={v[i]} onChange={(e) => setV(i, e.target.value)} />)}
            <button className="btn" onClick={() => run(resolve, "Disputa resolvida.")}>Definir resultado</button>
            {[m.player_a, m.player_b].map((p) => <button key={p} className="btn-gold btn" onClick={() => run(() => api(`/matches/${m.id}/wo/`, { method: "POST", body: { winner: p, reason: "WO aplicado pelo admin" } }), "WO aplicado.")}>WO para {n(p)}</button>)}
          </div>);
      })}
    </div>
  );
}

export function Admin({ sid }: { sid: number }) {
  const { n } = useNames(sid);
  const [msg, setMsg] = useState("");
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); setMsg(ok); } catch (x: any) { setMsg(x.message); } };
  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-center gap-3">
        <button className="btn-gold btn" onClick={() => run(() => api(`/seasons/${sid}/advance/`, { method: "POST" }), "Rodada ou fase gerada.")}>
          <FlagTriangleRight size={16} />Gerar próxima rodada ou fase</button>
        <label className="btn-soft cursor-pointer text-sm">
          <Upload size={16} />Importar jogadores (CSV)
          <input type="file" accept=".csv" className="hidden" onChange={(e) => { const f = new FormData(); f.append("file", e.target.files![0]);
            run(() => api(`/seasons/${sid}/import-csv/`, { method: "POST", form: f }), "Jogadores importados."); }} /></label>
        <label className="btn-soft cursor-pointer text-sm">
          <Upload size={16} />Importar inscrições (Excel)
          <input type="file" accept=".xlsx" className="hidden" onChange={(e) => { const f = new FormData(); f.append("file", e.target.files![0]);
            run(() => api(`/registrations/import/`, { method: "POST", form: f }), "Inscrições importadas — jogadores já podem fazer check-in pelo telefone."); }} /></label>
        <span className="text-sm text-teal">{msg}</span>
      </div>
      <p className="text-xs text-muted -mt-2">Importe a planilha de inscrições (aba "ea-sports-fc-26") uma vez; os jogadores entram sozinhos fazendo check-in pelo telefone na tela inicial.</p>
      <DisputesPanel sid={sid} n={n} />
      <RulesPanel sid={sid} />
      <DeadlinesPanel sid={sid} />
      <PlayersPanel sid={sid} />
    </div>
  );
}
