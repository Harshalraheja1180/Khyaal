"use client";

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Check, Heart, Volume2 } from "lucide-react";
import { api } from "@/lib/api";

type Choice = { id: string; label: string; emoji: string };
type Question = { id: string; prompt: string; scene: string; visual: string; choices: Choice[] };
export type WellbeingAnswer = { question_id: string; prompt: string; scene: string; answer_id: string; answer: string; emoji: string };
export type WellbeingResult = { submitted_at: string; overall_score: number | null; overall_category: string | null; category_scores: Record<string, number>; summary: string | null; answers: WellbeingAnswer[] };
export type TodayStatus = { date: string; completed: boolean; next_available_date: string; next_available_at: string; result: WellbeingResult | null };
export type WellbeingHistoryItem = { date: string | null; submitted_at: string; declined: boolean; overall_category: string | null; summary: string | null; response: { answers?: WellbeingAnswer[]; mood?: string } };
export type WellbeingReport = {
  today: string;
  today_result: WellbeingResult | null;
  completed_checkins: number;
  history: { date: string; overall_score: number; overall_category: string; category_scores: Record<string, number>; submitted_at: string }[];
  category_trends: Record<string, { label: string; previous_average: number | null; recent_average: number | null; change: number | null }>;
};

const sceneEmoji: Record<string, string> = {
  faces: "😊", celebration: "🎈", connection: "💌", helping: "🛍️",
  conversation: "🤝", new_path: "🗺️", small_win: "✨", activity: "🎵",
};
export const wellbeingCategories: [string, string][] = [
  ["mood", "Mood"], ["connection", "Connection"], ["awareness", "Emotional awareness"],
  ["empathy", "Empathy"], ["coping", "Coping"], ["confidence", "Confidence"], ["engagement", "Enjoyment"],
];
const displayDate = (value: string) => new Date(value).toLocaleDateString([], { weekday: "long", month: "long", day: "numeric" });
const displayTime = (value: string) => new Date(value).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

export function DailyCheckin({ dependentId, history, refresh }: { dependentId: string; history: WellbeingHistoryItem[]; refresh: () => Promise<void> }) {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [today, setToday] = useState<TodayStatus | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    if (!dependentId) return;
    setLoading(true);
    setError("");
    try {
      const [status, bank] = await Promise.all([
        api<TodayStatus>(`/dependents/${dependentId}/wellbeing/today`),
        api<Question[]>(`/dependents/${dependentId}/wellbeing/questions`),
      ]);
      setToday(status);
      setQuestions(bank);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Your check-in could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [dependentId]);
  useEffect(() => {
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  const submit = async () => {
    setSaving(true);
    setError("");
    try {
      const result = await api<TodayStatus>(`/dependents/${dependentId}/wellbeing-checkins`, {
        method: "POST",
        body: JSON.stringify({ answers }),
      });
      setToday(result);
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Your check-in could not be saved.");
      await load();
    } finally {
      setSaving(false);
    }
  };
  const readAloud = (text: string) => {
    if ("speechSynthesis" in window) {
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
    }
  };

  const result = today?.result;
  const currentQuestion = questions[step];
  const allAnswered = questions.length > 0 && questions.every((question) => answers[question.id]);

  return <div className="wellbeing-wrap">
    <div className="wellbeing-heading"><span className="eyebrow">A small moment for you</span><h1>How I Feel Today</h1><p>A gentle daily check-in. There are no right or wrong answers.</p></div>
    {error && <div role="alert" className="wellbeing-error">{error}</div>}
    {loading ? <div className="wellbeing-loading" role="status">Getting your check-in ready…</div> : today?.completed && result ? <>
      <section className="wellbeing-done" aria-labelledby="wellbeing-done-title"><div className="wellbeing-done-heart" aria-hidden="true">❤️</div><span className="eyebrow">Completed today</span><h2 id="wellbeing-done-title">You’re done for today.</h2><p>Thanks for checking in.</p><div className="wellbeing-result-label">{result.overall_category}</div>{result.summary && <p className="wellbeing-summary">{result.summary}</p>}<span className="wellbeing-completed-time">Completed at {displayTime(result.submitted_at)}</span><div className="wellbeing-next-date">Your next check-in will be ready {displayDate(today.next_available_date)}.</div></section>
      <History history={history}/>
    </> : !currentQuestion ? <div className="wellbeing-loading">Your check-in questions are not available right now.</div> : <>
      <div className="wellbeing-step-head"><span>Question {step + 1} of {questions.length}</span><span>{Math.round((step + 1) / questions.length * 100)}%</span></div>
      <div className="wellbeing-progress" role="progressbar" aria-label="Check-in progress" aria-valuemin={0} aria-valuemax={questions.length} aria-valuenow={step + 1}><span style={{ width: `${(step + 1) / questions.length * 100}%` }}/></div>
      <section className="wellbeing-question-card" aria-live="polite">
        <div className={`wellbeing-scene wellbeing-scene-${currentQuestion.visual}`} aria-hidden="true"><span className="wellbeing-scene-spark">✦</span><span className="wellbeing-character">{sceneEmoji[currentQuestion.visual] || "🌈"}</span><span className="wellbeing-scene-orb">●</span></div>
        <div className="wellbeing-question-top"><p>{currentQuestion.scene}</p><button className="wellbeing-listen" aria-label="Read this question aloud" onClick={() => readAloud(`${currentQuestion.scene}. ${currentQuestion.prompt}`)}><Volume2 size={20}/> Listen</button></div>
        <h2>{currentQuestion.prompt}</h2>
        <div className="wellbeing-choices">{currentQuestion.choices.map((choice, index) => <button key={choice.id} className={`wellbeing-choice ${answers[currentQuestion.id] === choice.id ? "selected" : ""}`} aria-pressed={answers[currentQuestion.id] === choice.id} onClick={() => setAnswers((current) => ({ ...current, [currentQuestion.id]: choice.id }))} style={{ "--choice-delay": `${index * 45}ms` } as React.CSSProperties}><span className="wellbeing-choice-emoji" aria-hidden="true">{choice.emoji}</span><span>{choice.label}</span>{answers[currentQuestion.id] === choice.id && <Check className="wellbeing-choice-check" size={19} aria-label="Selected"/>}</button>)}</div>
      </section>
      <div className="wellbeing-controls"><button className="btn secondary" disabled={step === 0} onClick={() => setStep((value) => Math.max(0, value - 1))}><ArrowLeft size={18}/> Back</button>{step < questions.length - 1 ? <button className="btn large wellbeing-next" disabled={!answers[currentQuestion.id]} onClick={() => setStep((value) => value + 1)}>Next <ArrowRight size={19}/></button> : <button className="btn large wellbeing-next" disabled={!allAnswered || saving} onClick={() => void submit()}>{saving ? "Saving…" : "Finish check-in"}<Heart size={19}/></button>}</div>
      <p className="wellbeing-gentle-note">You can take your time. This check-in will stay available today.</p>
      <History history={history}/>
    </>}
  </div>;
}

function History({ history }: { history: WellbeingHistoryItem[] }) {
  const past = history.filter((item) => item.overall_category || item.response?.mood).slice(0, 5);
  if (!past.length) return null;
  return <section className="wellbeing-history"><h2>Recent check-ins</h2>{past.map((item, i) => <div key={`${item.submitted_at}-${i}`} className="wellbeing-history-row"><span>{item.overall_category || `Feeling ${item.response.mood}`}</span><span>{item.date ? displayDate(item.date) : displayDate(item.submitted_at)}</span></div>)}</section>;
}
