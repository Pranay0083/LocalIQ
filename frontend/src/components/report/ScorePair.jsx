

/* The two composites: the reader's, in the data hue, beside the neutral baseline. */
export const ScorePair = ({ report }) => {
  const persona = report.composite?.score;
  const baseline = report.baseline_composite?.score;
  const gap = persona != null && baseline != null ? persona - baseline : null;
  return (
    <div className="flex items-end gap-8" data-testid="score-pair">
      <div>
        <p className="overline">Scored for you</p>
        <p className="mono text-[36px] font-semibold leading-none text-data" data-testid="persona-score">
          {persona ?? "—"}
        </p>
      </div>
      <div>
        <p className="overline">Neutral baseline</p>
        <p className="mono text-2xl leading-none text-zinc-50" data-testid="baseline-score">
          {baseline ?? "—"}
        </p>
      </div>
      <p className="max-w-[260px] pb-0.5 text-sm text-zinc-500">
        {gap == null
          ? "Not enough scored modules for a composite yet."
          : `${gap === 0 ? "Level with" : `${Math.abs(gap)} ${gap > 0 ? "above" : "below"}`} the baseline once weighted for ${report.persona_label?.toLowerCase()}.`}
      </p>
    </div>
  );
};

/* Signature: every module's score on a 0-100 track, with a tick at the Bengaluru median. */
