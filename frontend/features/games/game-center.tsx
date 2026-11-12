"use client";

import { useEffect, useState } from "react";
import { ArrowLeft, Sparkles, Volume2 } from "lucide-react";
import { api, Game } from "@/lib/api";

type GameKind = "sequence_memory" | "tile_memory" | "pattern_memory" | "matching_pairs" | "odd_one_out";
type Definition = { type: GameKind; title: string; emoji: string; color: string; description: string; instructions: string };

const catalog: Definition[] = [
  { type: "sequence_memory", title: "Sequence Memory", emoji: "🔴", color: "#fff1e9", description: "Watch the colorful lights, then tap them in order.", instructions: "Look closely as each color lights up. When they hide, tap the same colors in the same order." },
  { type: "tile_memory", title: "Tile Memory", emoji: "🟦", color: "#e8f4ff", description: "Remember the bright tiles in the grid.", instructions: "A few tiles will glow. When they fade, tap each tile you remember. Tap them in any order." },
  { type: "pattern_memory", title: "Pattern Memory", emoji: "✨", color: "#f1eaff", description: "Follow a little path of glowing stars.", instructions: "Watch the path light up one tile at a time. Tap the tiles in that same order." },
  { type: "matching_pairs", title: "Matching Pairs", emoji: "🌼", color: "#fff6df", description: "Turn over cards and find the matching pictures.", instructions: "Flip two cards at a time. Matching pictures stay up. See how many pairs you can find." },
  { type: "odd_one_out", title: "Odd One Out", emoji: "🔷", color: "#e8f7f1", description: "Find the one shape that is a little different.", instructions: "Look across the board and tap the picture that is different from the others." },
];

const pads = [
  { emoji: "●", color: "#f47e6c", name: "coral" },
  { emoji: "◆", color: "#5b91e8", name: "blue" },
  { emoji: "★", color: "#f2bd4b", name: "gold" },
  { emoji: "■", color: "#51ad8c", name: "green" },
];
const symbols = ["🌞", "🍎", "🐠", "🎈", "🌼", "🚲", "🍋", "⭐"];
const shuffle = <T,>(items: T[]) => [...items].sort(() => Math.random() - 0.5);
const sample = (count: number, limit: number) => shuffle(Array.from({ length: limit }, (_, i) => i)).slice(0, count);

export function GameCenter({
  isGuardian,
  dependentId,
  games,
  run,
}: {
  isGuardian: boolean;
  dependentId: string;
  games: Game[];
  run: (action: () => Promise<unknown>, success?: string) => Promise<void>;
}) {
  const [selected, setSelected] = useState<Definition | null>(null);
  const [phase, setPhase] = useState<"catalog" | "intro" | "playing" | "complete">("catalog");
  const [sessionId, setSessionId] = useState("");
  const [round, setRound] = useState(1);
  const [score, setScore] = useState(0);
  const [interactions, setInteractions] = useState(0);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const current = selected;
  const openGame = (definition: Definition) => {
    setSelected(definition);
    setPhase("intro");
    setRound(1);
    setScore(0);
    setInteractions(0);
    setError("");
  };
  const start = async () => {
    if (!current || !dependentId) return;
    setSaving(true);
    setError("");
    try {
      const session = await api<{ id: string }>(`/dependents/${dependentId}/game-sessions`, {
        method: "POST",
        body: JSON.stringify({ game_type: current.type }),
      });
      setSessionId(session.id);
      setPhase("playing");
    } catch (e) {
      setError(e instanceof Error ? e.message : "The game could not start. Please try again.");
    } finally {
      setSaving(false);
    }
  };
  const finish = async (completed: boolean, totalScore = score, finalRound = round, id = sessionId) => {
    if (!id) return;
    try {
      await api(`/game-sessions/${id}/finish`, {
        method: "POST",
        body: JSON.stringify({
          interactions,
          result: { game_type: current?.type, rounds_completed: completed ? 3 : finalRound - 1, score: totalScore, completed },
        }),
      });
    } catch {
      setError("Your game is finished, but the result could not be saved.");
    }
  };
  const exit = () => {
    if (phase === "playing") void finish(false);
    setSessionId("");
    setSelected(null);
    setPhase("catalog");
  };
  const playAgain = async () => {
    setPhase("intro");
    setRound(1);
    setScore(0);
    setInteractions(0);
    setSessionId("");
  };
  const advance = (points: number) => {
    const nextScore = score + points;
    setScore(nextScore);
    if (round >= 3) {
      setPhase("complete");
      void finish(true, nextScore, 3);
    } else {
      setRound((value) => value + 1);
    }
  };

  if (phase === "catalog") return <div className="game-center">
    <div className="game-heading"><div><span className="eyebrow">A little play, at your pace</span><h1>Games to enjoy</h1><p>Bright, familiar game patterns made for a relaxed moment.</p></div><div className="game-heading-icon" aria-hidden="true">🎨</div></div>
    {isGuardian && <div className="game-note"><Sparkles size={19}/><span>These are general games. They do not use family photos or private details.</span></div>}
    <div className="game-catalog">{catalog.map((item, index) => {
      const saved = games.find((game) => game.game_type === item.type);
      return <article key={item.type} className={`game-card game-card-${index + 1}`} style={{ background: item.color }}>
        <div className="game-card-emoji" aria-hidden="true">{item.emoji}</div><div className="game-card-copy"><span className="game-card-kicker">{saved ? "Ready to play" : "Play any time"}</span><h2>{item.title}</h2><p>{item.description}</p></div>
        {isGuardian ? saved ? <button className="game-card-badge game-pause-toggle" onClick={() => void run(() => api(`/games/${saved.id}`, { method: "PATCH", body: JSON.stringify({ active: !saved.active }) }), saved.active ? "Game paused." : "Game ready to play.")}>{saved.active ? "Pause for this person" : "Make available again"}</button> : <span className="game-card-badge">Ready for your care circle</span> : saved?.active === false ? <button className="btn game-play-button" disabled aria-label={`${item.title} is paused`}>Paused</button> : <button className="btn game-play-button" onClick={() => openGame(item)}>Play <span aria-hidden="true">→</span></button>}
      </article>;
    })}</div>
    {isGuardian && <p className="muted game-footnote">Your linked person can open Games from their own account. Every game is designed for enjoyment, not assessment.</p>}
  </div>;

  if (!current) return null;
  if (phase === "intro") return <div className="game-stage game-intro" style={{ "--game-tint": current.color } as React.CSSProperties}>
    <button className="game-back" onClick={exit}><ArrowLeft size={18}/> All games</button>
    <div className="game-intro-art" aria-hidden="true"><span>{current.emoji}</span><span>✨</span><span>🌈</span></div>
    <span className="eyebrow">A little game</span><h1>{current.title}</h1><p className="game-intro-copy">{current.instructions}</p>
    <div className="game-info-row"><span>3 short rounds</span><span>Large, easy-to-tap pieces</span><span>Play at your pace</span></div>
    {error && <p className="game-error" role="alert">{error}</p>}
    <button className="btn large game-main-button" disabled={saving} onClick={() => void start()}>{saving ? "Getting the game ready…" : "Let’s play"}<span aria-hidden="true">→</span></button>
  </div>;

  if (phase === "complete") return <div className="game-stage game-finish">
    <button className="game-back" onClick={exit}><ArrowLeft size={18}/> Exit</button>
    <div className="confetti" aria-hidden="true">{Array.from({ length: 18 }, (_, i) => <i key={i} style={{ "--i": i } as React.CSSProperties}/>)}</div>
    <div className="finish-orb" aria-hidden="true">🎉</div><span className="eyebrow">Lovely playing</span><h1>Three rounds complete!</h1><p>You made it through all the rounds. Thanks for playing.</p>
    <div className="finish-score"><span>Your score</span><strong>{score}</strong><span>points</span></div>
    {error && <p className="game-error" role="status">{error}</p>}
    <button className="btn large game-main-button" onClick={() => void playAgain()}>Play again <span aria-hidden="true">↻</span></button>
  </div>;

  return <div className="game-stage game-active">
    <div className="game-active-top"><button className="game-back" onClick={exit}><ArrowLeft size={18}/> Exit game</button><div className="game-live-score"><span>Score</span><strong>{score}</strong></div></div>
    <div className="game-progress-label"><div><span className="eyebrow">{current.title}</span><h1>Round {round} of 3</h1></div><span className="game-progress-count">{Math.round((round - 1) / 3 * 100)}% complete</span></div>
    <div className="game-progress-track" role="progressbar" aria-label="Game progress" aria-valuemin={0} aria-valuemax={3} aria-valuenow={round - 1}><span style={{ width: `${(round - 1) / 3 * 100}%` }}/></div>
    <GameRound key={`${current.type}-${round}`} definition={current} round={round} onInteraction={() => setInteractions((count) => count + 1)} onComplete={advance}/>
  </div>;
}

function GameRound({ definition, round, onInteraction, onComplete }: { definition: Definition; round: number; onInteraction: () => void; onComplete: (points: number) => void }) {
  const [feedback, setFeedback] = useState("");
  const [showing, setShowing] = useState(definition.type !== "matching_pairs" && definition.type !== "odd_one_out");
  const [flash, setFlash] = useState(0);
  const [picked, setPicked] = useState<number[]>([]);
  const [matched, setMatched] = useState<number[]>([]);
  const [openCards, setOpenCards] = useState<number[]>([]);
  const [locked, setLocked] = useState(false);
  const [sequence] = useState(() => Array.from({ length: 2 + round }, () => Math.floor(Math.random() * pads.length)));
  const [tilePattern] = useState(() => sample(2 + round, round === 1 ? 9 : 16));
  const [pathPattern] = useState(() => sample(2 + round, 9));
  const [cards] = useState(() => {
    const pairs = 3 + round;
    const selected = shuffle(symbols).slice(0, pairs);
    return shuffle(selected.flatMap((symbol) => [symbol, symbol]));
  });
  const [oddBoard] = useState(() => {
    const values = [9, 12, 16][round - 1];
    const base = symbols[Math.floor(Math.random() * symbols.length)];
    const different = symbols.filter((value) => value !== base)[Math.floor(Math.random() * (symbols.length - 1))];
    const index = Math.floor(Math.random() * values);
    return { values, base, different, index };
  });

  useEffect(() => {
    if (definition.type === "tile_memory") {
      const timer = window.setTimeout(() => setShowing(false), 1550);
      return () => window.clearTimeout(timer);
    }
    if (definition.type === "sequence_memory" || definition.type === "pattern_memory") {
      const length = definition.type === "sequence_memory" ? sequence.length : pathPattern.length;
      let cursor = 0;
      const timer = window.setInterval(() => {
        cursor += 1;
        if (cursor >= length) {
          setFlash(-1);
          setShowing(false);
          window.clearInterval(timer);
        } else setFlash(cursor);
      }, 560);
      return () => window.clearInterval(timer);
    }
    return undefined;
  }, [definition.type, pathPattern.length, sequence.length]);

  const sayInstructions = () => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(definition.instructions));
    }
  };
  const succeed = (points = 10) => {
    setLocked(true);
    setFeedback("Nice remembering! ✨");
    window.setTimeout(() => onComplete(points), 650);
  };
  const resetAfterMistake = (message: string) => {
    setLocked(true);
    setFeedback(message);
    setPicked([]);
    window.setTimeout(() => { setLocked(false); setFeedback(""); }, 1100);
  };

  if (definition.type === "sequence_memory") return <div className="round-panel"><div className="round-prompt"><div className="round-prompt-emoji" aria-hidden="true">{showing ? "👀" : "🎨"}</div><div><strong>{showing ? "Watch the colors" : "Your turn"}</strong><span>{showing ? "They will light up one by one." : "Tap the colors in the same order."}</span></div><button className="game-audio" aria-label="Read the instructions aloud" onClick={sayInstructions}><Volume2 size={19}/></button></div><div className="sequence-pads">{pads.map((pad, index) => <button key={pad.name} aria-label={`${pad.name} shape`} disabled={showing || locked} className={`sequence-pad ${flash === index && showing ? "is-lit" : ""}`} style={{ "--pad-color": pad.color } as React.CSSProperties} onClick={() => { onInteraction(); const next = [...picked, index]; setPicked(next); if (next.some((value, i) => value !== sequence[i])) resetAfterMistake("Not quite—let’s try that pattern again."); else if (next.length === sequence.length) succeed(); }}><span>{pad.emoji}</span></button>)}</div><div className="game-feedback" role="status">{feedback || (showing ? "Take your time…" : `${picked.length} of ${sequence.length} taps`)}</div></div>;

  if (definition.type === "tile_memory") {
    const size = round === 1 ? 3 : 4;
  return <div className="round-panel"><div className="round-prompt"><div className="round-prompt-emoji" aria-hidden="true">{showing ? "🌟" : "🟦"}</div><div><strong>{showing ? "Remember the glowing tiles" : "Tap the tiles you saw"}</strong><span>{showing ? "The bright tiles will hide in a moment." : "Any order is fine."}</span></div><button className="game-audio" aria-label="Read the instructions aloud" onClick={sayInstructions}><Volume2 size={19}/></button></div><div className="tile-board" style={{ "--tile-size": size } as React.CSSProperties}>{Array.from({ length: size * size }, (_, i) => <button key={i} aria-label={`Tile ${i + 1}${showing && tilePattern.includes(i) ? ", highlighted" : ""}`} className={`memory-tile ${showing && tilePattern.includes(i) ? "tile-glow" : picked.includes(i) ? "tile-picked" : ""}`} disabled={showing || locked} onClick={() => { onInteraction(); const next = [...picked, i]; setPicked(next); if (!tilePattern.includes(i)) resetAfterMistake("That’s okay—have another look at the pattern."); else if (next.length === tilePattern.length && tilePattern.every((item) => next.includes(item))) succeed(); }} />)}</div><div className="game-feedback" role="status">{feedback || (showing ? "A little pattern is appearing…" : `${picked.length} of ${tilePattern.length} tiles`)}</div></div>;
  }

  if (definition.type === "pattern_memory") return <div className="round-panel"><div className="round-prompt"><div className="round-prompt-emoji" aria-hidden="true">✨</div><div><strong>{showing ? "Follow the star path" : "Tap the path in order"}</strong><span>{showing ? "Watch the stars glow, one by one." : "Remember the same order."}</span></div><button className="game-audio" aria-label="Read the instructions aloud" onClick={sayInstructions}><Volume2 size={19}/></button></div><div className="pattern-board">{Array.from({ length: 9 }, (_, i) => <button key={i} aria-label={`Path tile ${i + 1}`} disabled={showing || locked} className={`memory-tile pattern-tile ${showing && pathPattern[flash] === i ? "tile-glow" : picked.includes(i) ? "tile-picked" : ""}`} onClick={() => { onInteraction(); const next = [...picked, i]; setPicked(next); if (pathPattern[next.length - 1] !== i) resetAfterMistake("Nearly—let’s follow that path again."); else if (next.length === pathPattern.length) succeed(); }} />)}</div><div className="game-feedback" role="status">{feedback || (showing ? "Watch the little trail…" : `${picked.length} of ${pathPattern.length} stars`)}</div></div>;

  if (definition.type === "matching_pairs") return <MatchingRound round={round} cards={cards} openCards={openCards} setOpenCards={setOpenCards} matched={matched} setMatched={setMatched} locked={locked} setLocked={setLocked} feedback={feedback} setFeedback={setFeedback} onInteraction={onInteraction} onComplete={succeed} />;

  return <div className="round-panel"><div className="round-prompt"><div className="round-prompt-emoji" aria-hidden="true">🔎</div><div><strong>Which picture is different?</strong><span>Look across the board, then tap one.</span></div><button className="game-audio" aria-label="Read the instructions aloud" onClick={sayInstructions}><Volume2 size={19}/></button></div><div className="odd-board" style={{ "--odd-cols": round === 1 ? 3 : 4 } as React.CSSProperties}>{Array.from({ length: oddBoard.values }, (_, i) => <button key={i} disabled={locked} className="odd-picture" aria-label={`Picture ${i + 1}`} onClick={() => { onInteraction(); if (i === oddBoard.index) succeed(); else resetAfterMistake("Keep looking—you’ll spot the different one."); }}>{i === oddBoard.index ? oddBoard.different : oddBoard.base}</button>)}</div><div className="game-feedback" role="status">{feedback || "Find the one that looks a little different."}</div></div>;
}

function MatchingRound({ round, cards, openCards, setOpenCards, matched, setMatched, locked, setLocked, feedback, setFeedback, onInteraction, onComplete }: {
  round: number; cards: string[]; openCards: number[]; setOpenCards: (value: number[]) => void; matched: number[]; setMatched: (value: number[]) => void; locked: boolean; setLocked: (value: boolean) => void; feedback: string; setFeedback: (value: string) => void; onInteraction: () => void; onComplete: (points: number) => void;
}) {
  const pairs = 3 + round;
  const flip = (index: number) => {
    if (locked || matched.includes(index) || openCards.includes(index)) return;
    onInteraction();
    const next = [...openCards, index];
    setOpenCards(next);
    if (next.length < 2) return;
    setLocked(true);
    if (cards[next[0]] === cards[next[1]]) {
      const found = [...matched, ...next];
      setMatched(found);
      setOpenCards([]);
      setFeedback("A lovely match! 🌼");
      window.setTimeout(() => {
        setLocked(false);
        setFeedback("");
        if (found.length === cards.length) onComplete(pairs * 5);
      }, 500);
    } else {
      setFeedback("No match this time—keep exploring.");
      window.setTimeout(() => { setOpenCards([]); setLocked(false); setFeedback(""); }, 850);
    }
  };
  return <div className="round-panel"><div className="round-prompt"><div className="round-prompt-emoji" aria-hidden="true">🌼</div><div><strong>Find the matching pairs</strong><span>{matched.length / 2} of {pairs} pairs found</span></div><span className="pairs-badge">{pairs} pairs</span></div><div className={`pairs-board ${cards.length > 10 ? "pairs-board-large" : ""}`}>{cards.map((card, index) => { const faceUp = matched.includes(index) || openCards.includes(index); return <button key={index} aria-label={faceUp ? `Picture ${card}` : "Turn over a card"} aria-pressed={faceUp} className={`pair-card ${faceUp ? "pair-card-up" : ""} ${matched.includes(index) ? "pair-card-matched" : ""}`} onClick={() => flip(index)}>{faceUp ? card : <span aria-hidden="true">✦</span>}</button>; })}</div><div className="game-feedback" role="status">{feedback || "Turn over two cards to find a pair."}</div></div>;
}
