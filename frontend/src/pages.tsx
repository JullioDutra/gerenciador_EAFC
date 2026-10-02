import { useEffect, useState, type ReactNode } from "react";
import {
  AlertTriangle, BarChart3, CalendarDays, CheckCircle2, Clock, Filter, FlagTriangleRight, Flame, Goal,
  Image as ImageIcon, ListOrdered, Scale, Settings2, Shield, ShieldAlert, Sparkles, Swords, Target, Trophy, Upload, UserCircle2, Users,
} from "lucide-react";
import { api, apiBlob, useData } from "./api";

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
const fmtDT = (v?: string | null) => (v ? new Date(v).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const groupName = (g: number | null) => (g ? `Grupo ${String.fromCharCode(64 + g)}` : "Sem grupo");
const toLocalInput = (v?: string | null) => { if (!v) return ""; const d = new Date(v); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };
const Err = ({ e }: { e: string }) => (e ? <p className="text-red-400 text-sm">{e}</p> : null);

export function Standings({ sid }: { sid: number }) {
  const { rows } = useNames(sid);
  const { data: season } = useData<any>(`/seasons/${sid}/`);
  const th = "px-2 py-2 text-right text-xs font-semibold uppercase tracking-wide text-muted";
  const groups = season?.config?.format === "groups";
  const buckets: [number | null, any[]][] = [];
  rows?.forEach((r) => { const g = groups ? r.group : null; let b = buckets.find((x) => x[0] === g); if (!b) buckets.push((b = [g, []])); b[1].push(r); });
  return (
    <div className="space-y-4">
      {buckets.map(([g, list]) => (
        <div key={g ?? "all"} className="card overflow-x-auto space-y-3">
          <SectionTitle icon={ListOrdered}>{groups ? groupName(g) : "Classificação"}</SectionTitle>
          <table className="w-full text-sm">
            <thead><tr><th className={th}>Pos</th><th className={th + " text-left"}>Jogador</th>
              {["J", "V", "E", "D", "GP", "GC", "SG", "Pts"].map((h) => <th key={h} className={th}>{h}</th>)}</tr></thead>
            <tbody>{list.map((r) => (
              <tr key={r.player.id} className={`border-l-2 border-t border-t-line ${ZONE[r.zone]}`}>
                <td className="px-2 py-1.5 text-right text-muted">{r.pos}</td>
                <td className="px-2 py-1.5 font-medium">{r.player.nickname}{r.player.team && <span className="text-muted font-normal"> ({r.player.team})</span>}</td>
                {[r.j, r.v, r.e, r.d, r.gp, r.gc, r.sg].map((v, i) => <td key={i} className="px-2 text-right text-muted">{v}</td>)}
                <td className="px-2 text-right font-bold text-gold">{r.pts}</td>
              </tr>))}</tbody>
          </table>
        </div>))}
      <div className="flex flex-wrap gap-3 text-xs text-muted pt-1">
        {groups ? <><span className="chip-teal">Classificado para o mata-mata</span><span className="chip-rose">Fora</span></>
          : <><span className="chip-teal">Classificação direta</span><span className="chip-gold">Playoff</span><span className="chip-rose">Eliminado</span></>}
      </div>
    </div>
  );
}

const FORMAT_LABEL: Record<string, string> = { single: "Partida única", bo3: "Melhor de 3", bo5: "Melhor de 5", two_legs: "Ida e volta" };
const legScore = (l: any) => (l.score_a === null ? "—" : `${l.score_a}-${l.score_b}${l.pen_a != null ? ` (${l.pen_a}-${l.pen_b} pên.)` : ""}${l.extra_time ? " pró." : ""}`);

function MatchRow({ m, n, extra }: { m: any; n: (i: number | null) => string; extra?: ReactNode }) {
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
      {extra && <div className="text-right mt-1">{extra}</div>}
      {(m.scheduled_at || m.deadline) && !DONE.includes(m.status) && (
        <p className="text-xs text-muted text-right mt-1 flex items-center justify-end gap-1.5"><Clock size={12} />
          {m.scheduled_at && <>Jogo: {fmtDT(m.scheduled_at)} · </>}placar até {fmtDT(m.deadline)}</p>
      )}
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
      <p className="text-sm">Informe o placar ({labelA} x {labelB}). Basta um dos dois lançar: o resultado já vale, e quem não lançou pode contestar.</p>
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
  const locked = !!nm?.deadline && new Date(nm.deadline).getTime() < Date.now();
  const contest = async (id: number) => { if (!confirm("Contestar este resultado? O organizador vai decidir.")) return; try { await api(`/matches/${id}/contest/`, { method: "POST" }); reload(); } catch (x: any) { alert(x.message); } };
  const stat = (t: string, v: any) => <div className="card text-center"><div className="font-display text-3xl font-extrabold text-gold">{v}</div><div className="text-xs text-muted mt-0.5">{t}</div></div>;
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="w-11 h-11 rounded-xl bg-panel2 flex items-center justify-center shrink-0"><Trophy size={22} className="text-gold" /></div>
        <div>
          <h2 className="text-2xl font-bold">Você está em {me.position}º lugar{me.group ? ` no ${groupName(me.group)}` : ""}</h2>
          {(me.player.team || me.player.campus) && <p className="text-sm text-muted">{me.player.team}{me.player.team && me.player.campus && " · "}{me.player.campus}</p>}
        </div>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {stat("Pontos", me.points)}{stat("V-E-D", me.record.join("-"))}{stat("Gols marcados", me.gf)}{stat("Saldo", me.gd)}</div>
      <div className="card space-y-2">
        <SectionTitle icon={Swords}>Próxima partida</SectionTitle>
        {nm ? <>
          <p>Adversário: <b>{n(nm.player_a === me.player.id ? nm.player_b : nm.player_a)}</b>{multi && <span className="text-muted text-sm"> · {FORMAT_LABEL[nm.match_format]}</span>}</p>
          <p className="text-sm text-muted flex items-center gap-1.5"><CalendarDays size={14} />{nm.scheduled_at && <>Jogo: {fmtDT(nm.scheduled_at)} · </>}placar até {nm.deadline ? fmtDT(nm.deadline) : "sem prazo"} <StatusChip status={nm.status} /></p>
          {multi && nm.legs?.length > 0 && (
            <ul className="text-sm text-muted">{nm.legs.map((l: any) => <li key={l.number}>Jogo {l.number}: {legScore(l)}</li>)}</ul>)}
          {nm.status === "disputed" ? <p className="text-sm text-gold">Resultado contestado: aguarde o organizador decidir.</p>
            : locked ? <p className="text-sm text-rose-300 flex items-center gap-1.5"><AlertTriangle size={15} />Prazo encerrado. Só o organizador pode liberar mais tempo ou lançar o placar.</p>
            : <ReportForm labelA={n(nm.player_a)} labelB={n(nm.player_b)} onSubmit={async (f) => {
              if (multi) f.append("leg_number", String(nextLeg));
              await api(`/matches/${nm.id}/${multi ? "report-leg" : "report"}/`, { method: "POST", form: f }); reload();
            }} />}
        </> : <p className="text-muted">Nenhuma partida pendente.</p>}
      </div>
      <div className="card"><SectionTitle icon={ListOrdered}>Histórico</SectionTitle>
        {me.history.length === 0 && <p className="text-muted text-sm mt-2">Nenhuma partida disputada ainda.</p>}
        {me.history.map((m: any) => <MatchRow key={m.id} m={m} n={n} extra={m.contestable && m.reported_by !== me.player.id &&
          <button className="text-xs text-rose-300 hover:underline" onClick={() => contest(m.id)}>Contestar resultado</button>} />)}</div>
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

/** Check-in do jogador: só o telefone, sem formulário. Busca as pré-inscrições (uma por campeonato) e já loga. */
export function CheckIn({ sid, onDone }: { sid?: number; onDone: (token: string, sid?: number) => void }) {
  const [phone, setPhone] = useState(""); const [reg, setReg] = useState<any>(); const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  const [picked, setPicked] = useState<number[]>([]);
  const lookup = async () => {
    setBusy(true); setErr("");
    try {
      const r = await api("/checkin/lookup/", { method: "POST", body: { phone } }); setReg(r);
      const ok = (r.registrations as any[]).filter((x) => x.season); setPicked(ok.length === 1 ? [ok[0].id] : []);
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const confirm = async (ids: number[]) => {
    if (ids.length === 0) { setErr("Escolha em qual campeonato fazer o check-in."); return; }
    setBusy(true); setErr("");
    try { const r = await api("/checkin/confirm/", { method: "POST", body: { phone, season: sid, registrations: ids } }); onDone(r.token, r.seasons?.[0]); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  if (reg) {
    const regs: any[] = reg.registrations ?? []; const avail = regs.filter((x) => x.season);
    const multi = regs.length > 1;
    const toggle = (id: number) => setPicked((p) => (p.includes(id) ? p.filter((x) => x !== id) : [...p, id]));
    return (
      <div className="card space-y-3">
        <p className="text-sm text-muted">Encontramos sua inscrição:</p>
        <div className="bg-panel2 rounded-xl p-3 space-y-1">
          <p className="font-display text-xl font-bold">{reg.nome}</p>
          <p className="text-sm text-muted">{reg.equipe && <>Time: <span className="text-ice">{reg.equipe}</span> · </>}{reg.campus}</p>
          {reg.curso && <p className="text-xs text-muted">{reg.curso}</p>}
        </div>
        {multi && <p className="text-sm">Seu número está em <b>{regs.length} campeonatos</b>. Em qual deles você quer fazer o check-in?</p>}
        <div className="space-y-2">
          {regs.map((x) => (
            <label key={x.id} className={`flex items-center gap-3 rounded-xl border border-line p-3 text-sm ${x.season ? "cursor-pointer hover:bg-panel2" : "opacity-50"}`}>
              {multi && <input type="checkbox" disabled={!x.season} checked={picked.includes(x.id)} onChange={() => toggle(x.id)} />}
              <span className="flex-1"><b>{x.jogo || "Campeonato"}</b>{x.equipe && <span className="text-muted"> · {x.equipe}</span>}
                <span className="block text-xs text-muted">{x.season ? x.season.name : "Nenhum campeonato aberto para esta inscrição ainda."}</span></span>
              {x.already_checked_in && <span className="chip-gold"><CheckCircle2 size={12} />Já fez</span>}
            </label>))}
        </div>
        {!multi && regs[0]?.already_checked_in && <p className="text-xs text-gold flex items-center gap-1"><CheckCircle2 size={13} />Você já fez check-in antes — confirmar de novo só entra na sua conta.</p>}
        <Err e={err} />
        <div className="flex flex-wrap gap-2">
          <button className="btn-soft btn flex-1 justify-center" onClick={() => setReg(undefined)}>Não sou eu</button>
          {multi ? <>
            <button className="btn flex-1 justify-center" onClick={() => confirm(picked)} disabled={busy || picked.length === 0}>{busy ? "Entrando…" : `Check-in nos selecionados (${picked.length})`}</button>
            {avail.length > 1 && <button className="btn-gold btn flex-1 justify-center" onClick={() => confirm(avail.map((x) => x.id))} disabled={busy}>Nos dois / todos</button>}
          </> : <button className="btn flex-1 justify-center" onClick={() => confirm(avail.map((x) => x.id))} disabled={busy || avail.length === 0}>{busy ? "Entrando…" : "Confirmar check-in"}</button>}
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
  const [f, setF] = useState({ name: "Temporada", year: String(thisYear), jogo: "", format: "league", groups: "4", group_qualify: "2",
    swiss_rounds: "8", direct: "16", playoff_size: "48", playoff_qualify: "16" });
  const isGroups = f.format === "groups";
  const koSize = Number(f.groups || 0) * Number(f.group_qualify || 0);
  const koOk = [2, 4, 8, 16, 32].includes(koSize);
  const [msg, setMsg] = useState("");
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const total = Number(f.direct || 0) + Number(f.playoff_size || 0);
  const create = async () => {
    try {
      if (isGroups && !koOk) { setMsg(`Grupos × classificados por grupo = ${koSize}. Use 2, 4, 8, 16 ou 32 para montar o mata-mata.`); return; }
      const s = await api("/seasons/", { method: "POST", body: {
        name: f.name, year: Number(f.year), jogo: f.jogo.trim(),
        config: isGroups ? { format: "groups", groups: Number(f.groups), group_qualify: Number(f.group_qualify) }
          : { format: "league", swiss_rounds: Number(f.swiss_rounds), direct: Number(f.direct), playoff_size: Number(f.playoff_size), playoff_qualify: Number(f.playoff_qualify) },
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
      <label className="text-sm block"><span className="text-muted">Campeonato/jogo da inscrição (opcional — liga o check-in a esta temporada)</span>
        <input className="inp mt-1" placeholder="ex.: ea-sports-fc-26" value={f.jogo} onChange={(e) => set("jogo", e.target.value)} /></label>
      <div>
        <span className="text-sm text-muted">Formato da primeira fase</span>
        <div className="flex gap-2 mt-1">
          {[["league", "Fase de liga"], ["groups", "Fase de grupos"]].map(([k, t]) => (
            <button key={k} type="button" onClick={() => set("format", k)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${f.format === k ? "bg-royal text-white" : "bg-panel2 border border-line text-muted hover:text-ice"}`}>{t}</button>))}
        </div>
      </div>
      {isGroups ? <>
        <div className="flex flex-wrap gap-3">
          {field("groups", "Quantidade de grupos")}
          {field("group_qualify", "Classificam por grupo")}
        </div>
        <p className="text-xs text-muted">
          Os jogadores são sorteados em {f.groups} grupos e jogam todos contra todos dentro do grupo. Os {f.group_qualify} primeiros de cada grupo
          seguem para o mata-mata ({koSize || 0} classificados{koOk ? "" : " — use 2, 4, 8, 16 ou 32"}).
        </p>
      </> : <>
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
      </>}
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
        {cfg.format === "groups"
          ? <>{field("groups", "Grupos")}{field("group_qualify", "Classificam por grupo")}</>
          : <>{field("swiss_rounds", "Rodadas da liga")}{field("direct", "Classificação direta")}
            {field("playoff_size", "Tamanho do playoff")}{field("playoff_qualify", "Classificados do playoff")}</>}
        {field("round_days", "Dias por rodada")}{field("score_deadline_hours", "Prazo do placar (h)")}
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
  const { data: season } = useData<any>(`/seasons/${sid}/`);
  const groups = season?.config?.format === "groups"; const nGroups = Number(season?.config?.groups ?? 4);
  const [msg, setMsg] = useState(""); const [pen, setPen] = useState<Record<number, string>>({}); const [reason, setReason] = useState<Record<number, string>>({});
  const run = async (fn: () => Promise<any>, ok: string) => { try { await fn(); setMsg(ok); reload(); } catch (x: any) { setMsg(x.message); } };
  return (
    <div className="card space-y-2">
      <SectionTitle icon={Users}>Jogadores</SectionTitle>
      <span className="text-sm text-teal">{msg}</span>
      {groups && <button className="btn-soft btn" onClick={() => confirm("Sortear os grupos de novo? Só é possível antes da 1ª rodada.") && run(() => api(`/seasons/${sid}/draw-groups/`, { method: "POST" }), "Grupos sorteados.")}>
        <Shield size={16} />Sortear grupos</button>}
      <div className="max-h-96 overflow-y-auto space-y-1">
        {players?.map((p) => (
          <div key={p.id} className="flex flex-wrap items-center gap-2 py-1.5 border-t border-line text-sm">
            <span className="flex-1 font-medium">{p.nickname}</span>
            {groups && <select className="inp !w-28 !py-1" value={p.group ?? ""} onChange={(e) => run(() => api(`/players/${p.id}/`, { method: "PATCH", body: { group: e.target.value ? Number(e.target.value) : null } }), "Grupo atualizado.")}>
              <option value="">Sem grupo</option>{Array.from({ length: nGroups }, (_, i) => <option key={i} value={i + 1}>{groupName(i + 1)}</option>)}</select>}
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
      <p className="text-xs text-muted">Mudar o formato só afeta jogos ainda não iniciados nesta rodada. Mudar o prazo da rodada vale para as partidas que ainda seguiam o prazo antigo.</p>
    </div>
  );
}

/** Admin: prazo de cada partida pendente. Passou do prazo, os jogadores não lançam mais placar — só o admin libera mais tempo. */
function MatchDeadlinesPanel({ sid, n }: { sid: number; n: (i: number | null) => string }) {
  const { data: rounds } = useData<any[]>(`/rounds/?season=${sid}`);
  const [rid, setRid] = useState<number>(); const cur = rid ?? rounds?.at(-1)?.id;
  const { data: ms, reload } = useData<any[]>(cur ? `/matches/?round=${cur}` : null);
  const [msg, setMsg] = useState(""); const [val, setVal] = useState<Record<number, string>>({});
  const extend = async (id: number, hours?: number) => {
    const m = ms!.find((x) => x.id === id)!;
    const iso = hours ? new Date(Math.max(Date.now(), new Date(m.deadline ?? Date.now()).getTime()) + hours * 3600e3).toISOString() : new Date(val[id]).toISOString();
    try { await api(`/matches/${id}/extend-deadline/`, { method: "POST", body: { deadline: iso } }); setMsg("Prazo atualizado."); reload(); } catch (x: any) { setMsg(x.message); }
  };
  const open = ms?.filter((m) => !DONE.includes(m.status) && m.player_b);
  return (
    <div className="card space-y-2">
      <SectionTitle icon={Clock}>Liberar mais tempo para o placar</SectionTitle>
      <div className="flex flex-wrap gap-1.5">{rounds?.map((r) => (
        <button key={r.id} onClick={() => setRid(r.id)} className={`px-3 py-1 rounded-lg text-sm ${cur === r.id ? "bg-royal text-white" : "bg-panel2 border border-line text-muted"}`}>{r.name}</button>))}</div>
      <span className="text-sm text-teal">{msg}</span>
      {open?.length === 0 && <p className="text-muted text-sm">Nenhuma partida pendente nesta rodada.</p>}
      {open?.map((m) => {
        const late = m.deadline && new Date(m.deadline).getTime() < Date.now();
        return (
          <div key={m.id} className="flex flex-wrap items-center gap-2 py-1.5 border-t border-line text-sm">
            <span className="flex-1">{n(m.player_a)} x {n(m.player_b)} <span className={late ? "text-rose-300" : "text-muted"}>· até {fmtDT(m.deadline)}{late && " (encerrado)"}</span></span>
            <button className="btn-soft btn !py-1 !px-2" onClick={() => extend(m.id, 24)}>+24h</button>
            <input className="inp !w-52 !py-1" type="datetime-local" value={val[m.id] ?? toLocalInput(m.deadline)} onChange={(e) => setVal({ ...val, [m.id]: e.target.value })} />
            <button className="btn !py-1 !px-2" disabled={!(val[m.id])} onClick={() => extend(m.id)}>Definir</button>
          </div>);
      })}
    </div>
  );
}

/** Admin: gera a imagem dos confrontos de uma rodada (ou de um grupo/jogo) para conferir e mandar no grupo. */
function ImagesPanel({ sid }: { sid: number }) {
  const { data: rounds } = useData<any[]>(`/rounds/?season=${sid}`);
  const { data: season } = useData<any>(`/seasons/${sid}/`);
  const [rid, setRid] = useState<number>(); const [group, setGroup] = useState(""); const [url, setUrl] = useState<string>(); const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const cur = rounds?.find((r) => r.id === rid) ?? rounds?.at(-1);
  const nGroups = cur?.phase === "groups" ? Number(season?.config?.groups ?? 0) : 0;
  const make = async () => {
    if (!cur) return; setBusy(true); setMsg("");
    try { const b = await apiBlob(`/rounds/${cur.id}/image/${group ? `?group=${group}` : ""}`); setUrl((old) => { if (old) URL.revokeObjectURL(old); return URL.createObjectURL(b); }); }
    catch (x: any) { setMsg(x.message); } finally { setBusy(false); }
  };
  const fileName = `confrontos-${(cur?.name ?? "rodada").toLowerCase().replace(/\s+/g, "-")}${group ? `-grupo-${String.fromCharCode(64 + Number(group))}` : ""}.png`;
  const share = async () => {
    const blob = await (await fetch(url!)).blob(); const file = new File([blob], fileName, { type: "image/png" });
    if ((navigator as any).canShare?.({ files: [file] })) { try { await navigator.share({ files: [file], title: cur?.name }); } catch { /* cancelado */ } }
    else setMsg("Seu navegador não abre o compartilhamento: use Baixar e envie no grupo.");
  };
  return (
    <div className="card space-y-3">
      <SectionTitle icon={ImageIcon}>Imagem dos confrontos</SectionTitle>
      <div className="flex flex-wrap gap-1.5">{rounds?.map((r) => (
        <button key={r.id} onClick={() => { setRid(r.id); setGroup(""); setUrl(undefined); }} className={`px-3 py-1 rounded-lg text-sm ${cur?.id === r.id ? "bg-royal text-white" : "bg-panel2 border border-line text-muted"}`}>{r.name}</button>))}</div>
      <div className="flex flex-wrap items-center gap-2">
        {nGroups > 0 && <select className="inp !w-40 !py-1.5" value={group} onChange={(e) => { setGroup(e.target.value); setUrl(undefined); }}>
          <option value="">Todos os grupos</option>{Array.from({ length: nGroups }, (_, i) => <option key={i} value={i + 1}>{groupName(i + 1)}</option>)}</select>}
        <button className="btn" onClick={make} disabled={busy || !cur}>{busy ? "Gerando…" : "Gerar imagem"}</button>
        {url && <>
          <a className="btn-soft btn" href={url} download={fileName}>Baixar</a>
          <button className="btn-soft btn" onClick={share}>Compartilhar</button></>}
        <span className="text-sm text-rose-300">{msg}</span>
      </div>
      {url && <img src={url} alt="Confrontos da rodada" className="max-w-full rounded-xl border border-line" style={{ maxHeight: 640 }} />}
    </div>
  );
}

/** Admin: gera rodadas — várias de uma vez, com horário das partidas e prazo máximo para lançar o placar. */
function GeneratePanel({ sid }: { sid: number }) {
  const { data: season } = useData<any>(`/seasons/${sid}/`);
  const [f, setF] = useState({ count: "1", start: "", slot_minutes: "0", parallel: "0", round_gap_hours: "24", deadline_hours: "24" });
  const [msg, setMsg] = useState(""); const [busy, setBusy] = useState(false);
  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  const go = async () => {
    setBusy(true); setMsg("");
    try {
      const r = await api(`/seasons/${sid}/advance/`, { method: "POST", body: { count: Number(f.count) || 1, start: f.start ? new Date(f.start).toISOString() : undefined,
        slot_minutes: Number(f.slot_minutes) || 0, parallel: Number(f.parallel) || 0, round_gap_hours: Number(f.round_gap_hours) || 0, deadline_hours: Number(f.deadline_hours) || 24 } });
      setMsg(`${r.length} ${r.length === 1 ? "rodada gerada" : "rodadas geradas"}: ${r.map((x: any) => x.name).join(", ")}.`);
    } catch (x: any) { setMsg(x.message); } finally { setBusy(false); }
  };
  const num = (k: keyof typeof f, label: string, hint?: string) => (
    <label className="text-sm block"><span className="text-muted">{label}</span>
      <input className="inp mt-1 !w-28" type="number" min={0} value={f[k]} onChange={(e) => set(k, e.target.value)} title={hint} /></label>);
  return (
    <div className="card space-y-3">
      <SectionTitle icon={FlagTriangleRight}>Gerar rodadas</SectionTitle>
      <div className="flex flex-wrap items-end gap-3">
        {num("count", "Rodadas de uma vez", "Quantas rodadas gerar agora (liga/grupos)")}
        <label className="text-sm block"><span className="text-muted">Horário do 1º jogo</span>
          <input className="inp mt-1 !w-52" type="datetime-local" value={f.start} onChange={(e) => set("start", e.target.value)} /></label>
        {num("parallel", "Jogos ao mesmo tempo", "0 = todos juntos")}
        {num("slot_minutes", "Intervalo entre blocos (min)")}
        {num("round_gap_hours", "Intervalo entre rodadas (h)")}
        {num("deadline_hours", "Prazo p/ placar após o jogo (h)", "Depois disso só o admin libera mais tempo")}
      </div>
      <p className="text-xs text-muted">
        {season?.config?.format === "groups" ? "Fase de grupos: os grupos são sorteados na 1ª geração (ou em Jogadores → Sortear grupos) e cada rodada traz um jogo de cada jogador do grupo. "
          : "Rodadas geradas de uma vez usam a classificação atual e não repetem confrontos. "}
        Sem horário, o prazo conta a partir de agora. Quando terminar a liga/grupos, o mesmo botão monta a próxima fase.
      </p>
      <div className="flex items-center gap-3">
        <button className="btn-gold btn" onClick={go} disabled={busy}><FlagTriangleRight size={16} />{busy ? "Gerando…" : "Gerar"}</button>
        <span className="text-sm text-teal">{msg}</span>
      </div>
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
      <GeneratePanel sid={sid} />
      <ImagesPanel sid={sid} />
      <DisputesPanel sid={sid} n={n} />
      <MatchDeadlinesPanel sid={sid} n={n} />
      <RulesPanel sid={sid} />
      <DeadlinesPanel sid={sid} />
      <PlayersPanel sid={sid} />
    </div>
  );
}
