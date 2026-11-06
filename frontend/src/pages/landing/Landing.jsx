import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight } from "@phosphor-icons/react";
import snapshot from "./lens-snapshot.json";
import "./landing.css";

/* The fixed half of the page is one real LocalIQ dossier. Its module scores never change; switching
   the reader re-weights them with the rubric's own arithmetic (rubric.composite), so the score shown
   here is the score the app would print for the same data. */

const PHOTOS = {
  whitefield: {
    src: "/assets/sobha-rose-whitefield-road-3-24-2012.jpg",
    alt: "A white apartment tower on Whitefield Road under a clear sky",
    caption: "Whitefield Road",
  },
  indiranagar: {
    src: "/assets/indiranagar-shopping-hundred-feet-road-indiranagar-bangalore.jpg",
    alt: "Shopfronts lit up on 100 Feet Road, Indiranagar, at night",
    caption: "100 Feet Road, Indiranagar",
  },
  jayanagar: {
    src: "/assets/jayanagar-bangalore.jpg",
    alt: "A BBMP street sign for 15th Main Road, 4th T Block, under rain trees in Jayanagar",
    caption: "15th Main Road, Jayanagar 4th T Block",
  },
};

const CREDITS = [
  ["Sobha Rose, Whitefield Road", "Amol.Gaitonde", "CC BY-SA 3.0", "https://commons.wikimedia.org/wiki/File:Sobha_Rose,_Whitefield_Road_3-24-2012_5-25-54_PM.JPG"],
  ["Indiranagar Shopping Hundred Feet Road by night", "Indiranagar Seller", "CC BY-SA 4.0", "https://commons.wikimedia.org/w/index.php?curid=38006316"],
  ["Jayanagar, Bangalore", "LittleT889", "CC BY-SA 4.0", "https://commons.wikimedia.org/w/index.php?curid=86983201"],
  ["Map of Namma Metro Bengaluru, phases 1 to 3", "Ritgvs", "CC BY-SA 4.0", "https://commons.wikimedia.org/wiki/File:Map_of_Namma_Metro_Bengaluru_-_Phases_1_to_3.png"],
  ["Banashankari traffic circle (2024) 01", "Gpkp", "CC BY-SA 4.0", "https://commons.wikimedia.org/w/index.php?curid=152061270"],
  ["Cubbon Park, Bangalore, colonial postcard", "TuckDB Postcards", "CC BY 4.0", "https://commons.wikimedia.org/wiki/File:Cubbon_Park,_Bangalore_-_Colonial_India.jpg"],
];

const composite = (scores, weights) => {
  let num = 0;
  let den = 0;
  Object.entries(scores).forEach(([module, score]) => {
    const w = weights[module] || 0;
    if (score == null || !w) return;
    num += score * w;
    den += w;
  });
  return den ? Math.round(num / den) : null;
};

const NEUTRAL = Object.fromEntries(Object.keys(snapshot.modules).map((m) => [m, 1]));

/* Counts toward a new figure so a re-score is seen, not only read. */
const useTween = (value, ms = 520) => {
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (value == null) return setShown(value);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const start = performance.now();
    const a = from.current ?? value;
    let raf;
    const step = (t) => {
      const k = reduce ? 1 : Math.min(1, (t - start) / ms);
      const eased = 1 - Math.pow(1 - k, 3);
      setShown(Math.round(a + (value - a) * eased));
      if (k < 1) raf = requestAnimationFrame(step);
      else from.current = value;
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value, ms]);
  return shown;
};

const Report = ({ locality, persona }) => {
  const score = composite(locality.scores, persona.weights);
  const baseline = composite(locality.scores, NEUTRAL);
  const shownScore = useTween(score);
  const rows = Object.entries(persona.weights)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1] || (locality.scores[b[0]] ?? -1) - (locality.scores[a[0]] ?? -1))
    .slice(0, 6);
  return (
    <div className="ld-report" data-ui aria-live="polite">
      <div className="ld-report-head">
        <div>
          <p className="ld-report-name">{locality.name}</p>
          <p className="ld-report-meta">
            {locality.pincode} · {locality.zone} Bengaluru · for {persona.label.toLowerCase()}
          </p>
        </div>
        <div className="ld-report-scores">
          <p>
            <span className="ld-report-label">For you</span>
            <span className="ld-report-score">{shownScore ?? "—"}</span>
          </p>
          <p>
            <span className="ld-report-label">Baseline</span>
            <span className="ld-report-base">{baseline ?? "—"}</span>
          </p>
        </div>
      </div>
      <ul className="ld-ledger">
        {rows.map(([m, w]) => {
          const s = locality.scores[m];
          const median = snapshot.city_median[m];
          return (
            <li key={m}>
              <span className="ld-ledger-name">
                {snapshot.modules[m]} <span className="ld-ledger-w">×{w}</span>
              </span>
              <span className="ld-ledger-track">
                <span className="ld-ledger-bar" style={{ transform: `scaleX(${(s ?? 0) / 100})` }} />
                {median != null ? <span className="ld-ledger-tick" style={{ left: `${median}%` }} /> : null}
              </span>
              <span className={`ld-ledger-score ${s == null ? "is-absent" : ""}`}>{s == null ? "No data" : Math.round(s)}</span>
            </li>
          );
        })}
      </ul>
      <p className="ld-report-foot">Tick: Bengaluru median across {snapshot.city_localities} localities</p>
    </div>
  );
};

export default function Landing() {
  const [slug, setSlug] = useState("whitefield");
  const [personaKey, setPersonaKey] = useState("family_kids");
  const wordRef = useRef(null);
  const locality = snapshot.localities.find((l) => l.slug === slug);
  const persona = snapshot.personas.find((p) => p.key === personaKey) || snapshot.personas[0];

  const spread = useMemo(() => {
    const all = snapshot.personas.map((p) => composite(locality.scores, p.weights)).filter((v) => v != null);
    return [Math.min(...all), Math.max(...all)];
  }, [locality]);

  const topModules = Object.entries(persona.weights)
    .filter(([, w]) => w === 3)
    .map(([m]) => snapshot.modules[m].toLowerCase());

  useEffect(() => {
    const root = document.documentElement;
    root.classList.add("ld-motion");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const io = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("is-in")),
      { rootMargin: "0px 0px -12% 0px" },
    );
    document.querySelectorAll(".ld-reveal").forEach((el) => io.observe(el));
    // The fixed stage follows the story: a section that talks about a locality shows that locality.
    const stageIo = new IntersectionObserver(
      (entries) => entries.forEach((e) => e.isIntersecting && setSlug(e.target.dataset.stage)),
      { rootMargin: "-45% 0px -45% 0px" },
    );
    document.querySelectorAll("[data-stage]").forEach((el) => stageIo.observe(el));
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const k = Math.min(1, window.scrollY / window.innerHeight);
        if (wordRef.current) wordRef.current.style.transform = `scale(${1 - 0.07 * k})`;
      });
    };
    if (!reduce) window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      io.disconnect();
      stageIo.disconnect();
      window.removeEventListener("scroll", onScroll);
      root.classList.remove("ld-motion");
    };
  }, []);

  return (
    <div className="ld">
      <nav className="ld-nav" aria-label="Main">
        <a href="#how">How it works</a>
        <a href="#measured">What it measures</a>
        <a href="#pricing">Pricing</a>
        <Link to="/auth" data-testid="landing-signin">Sign in</Link>
        <Link to="/auth?mode=register" className="ld-nav-action" data-testid="landing-cta-top">
          Get 5 free reports
        </Link>
      </nav>

      <div className="ld-split">
        <aside className="ld-stage" aria-label="A live LocalIQ report">
          {Object.entries(PHOTOS).map(([key, p]) => (
            <img
              key={key}
              src={p.src}
              alt={p.alt}
              width="1200"
              height="1600"
              className={`ld-stage-photo ${key === slug ? "is-on" : ""}`}
              aria-hidden={key !== slug}
            />
          ))}
          <p className="ld-stage-caption">{PHOTOS[slug].caption}</p>
          <Report locality={locality} persona={persona} />
        </aside>

        <main className="ld-column">
          <header className="ld-hero">
            <h1>
              <span ref={wordRef} className="ld-wordmark">localiq</span>
              <span className="ld-h1-line">Neighbourhood scores for Bengaluru</span>
            </h1>
            <p className="ld-lead">
              Pick a locality and who you are. A team of agents gathers the facts, a published rubric scores
              them, and every number links to the page it came from.
            </p>
            <div className="ld-actions">
              <Link to="/auth?mode=register" className="ld-button" data-testid="landing-cta-main">
                Build my first report <ArrowRight size={16} />
              </Link>
              <Link to="/auth" className="ld-textlink" data-testid="landing-cta-secondary">
                I already have an account
              </Link>
            </div>
          </header>

          <section className="ld-section ld-reveal" aria-labelledby="lens-h">
            <h2 id="lens-h">One dossier, six readers</h2>
            <p>
              {locality.name}&rsquo;s facts do not change when you do; the weights do. Choose who is
              reading and the fixed report re-scores on the spot, with the same arithmetic the app runs
              on real data.
            </p>
            <div className="ld-tabs" role="group" aria-label="Who is reading">
              {snapshot.personas.map((p) => (
                <button
                  key={p.key}
                  type="button"
                  aria-pressed={p.key === personaKey}
                  onClick={() => setPersonaKey(p.key)}
                  className="ld-tab"
                >
                  {p.label.replace(" / Young professional", "").replace(" / ROI", "")}
                </button>
              ))}
            </div>
            <div className="ld-tabs ld-tabs-small" role="group" aria-label="Which locality">
              {snapshot.localities.map((l) => (
                <button key={l.slug} type="button" aria-pressed={l.slug === slug} onClick={() => setSlug(l.slug)} className="ld-tab">
                  {l.name}
                </button>
              ))}
            </div>
            <p className="ld-note">
              Weighs {topModules.slice(0, 4).join(", ")} three times.{" "}
              {locality.name} ranges from {spread[0]} to {spread[1]} across the six readers.
            </p>
            <div className="ld-phone-report">
              <Report locality={locality} persona={persona} />
            </div>
          </section>

          <section id="how" className="ld-section ld-reveal" aria-labelledby="how-h" data-stage="whitefield">
            <h2 id="how-h">One run, start to finish</h2>
            <p>
              Expensive collection runs once per locality and is shared by every reader. Your report is
              a thin personal pass over that dossier, which is why a cached locality opens in seconds.
            </p>
            <div className="ld-slip" role="table" aria-label="What one report run does">
              {[
                ["Intake", "locality and lens", "13 of 20 modules"],
                ["Collectors", "air, map, news, residents", "in parallel"],
                ["Verifier", "drops what it cannot trace", "27 kept · 0 dropped"],
                ["Scorer", "published rubric", "no language model"],
                ["Synthesiser", "the only writer", "verified facts only"],
              ].map(([a, b, c]) => (
                <div className="ld-slip-row" role="row" key={a}>
                  <span role="cell" className="ld-slip-what"><strong>{a}</strong> <span>{b}</span></span>
                  <span role="cell" className="ld-slip-value">{c}</span>
                </div>
              ))}
              <div className="ld-slip-row ld-slip-total" role="row">
                <span role="cell" className="ld-slip-what"><strong>A cached report</strong></span>
                <span role="cell" className="ld-slip-value">12.7 s median · $0.034 average</span>
              </div>
            </div>
          </section>

          <section id="measured" className="ld-section ld-reveal" aria-labelledby="measured-h" data-stage="indiranagar">
            <h2 id="measured-h">Distances are geometry</h2>
            <p>
              The nearest metro to Indiranagar is 232 m away because OpenStreetMap places the station
              there, not because a model guessed. Walking times, bus stops within 1.2 km and the count of
              hospitals are computed, never written.
            </p>
            <figure className="ld-figure">
              <img src="/assets/map-of-namma-metro-bengaluru-phases-1.png" alt="Network map of Namma Metro, Bengaluru, phases 1 to 3" width="1069" height="916" loading="lazy" />
              <figcaption>Namma Metro, phases 1 to 3: every station is a point the scorer measures to.</figcaption>
            </figure>
            <h3>Missing is a finding</h3>
            <p>
              When a layer has no data, the report says so and leaves it out of the average. A
              locality is never given Bengaluru&rsquo;s mean for a thing nobody measured.
            </p>
            <figure className="ld-figure">
              <video
                src="/assets/banashankari-traffic-circle-banashankari-bangalore-2024-01.webm"
                poster="/assets/banashankari-traffic-circle-banashankari-bangalore-2024-01-poster.jpg"
                autoPlay muted loop playsInline width="854" height="480"
                aria-label="Buses circling the Banashankari traffic circle under the metro line"
              />
              <figcaption>Banashankari traffic circle, one of the 34 localities, scored the same way.</figcaption>
            </figure>
          </section>

          <section className="ld-section ld-reveal" aria-labelledby="data-h">
            <h2 id="data-h" className="ld-h-small">Built on open data</h2>
            <p className="ld-sources">OpenStreetMap · OpenWeather · CPCB · Google News · Wikipedia · Reddit</p>
          </section>

          <section id="pricing" className="ld-section ld-reveal" aria-labelledby="pricing-h" data-stage="jayanagar">
            <h2 id="pricing-h">What it costs</h2>
            <dl className="ld-menu">
              {[
                ["Free", "₹0", "Five full locality reports, grounded chat and a citation on every number."],
                ["Pro, monthly", "₹499", "Unlimited reports and regeneration, side-by-side comparison, recommendation runs."],
                ["Pro, yearly", "₹4,499", "Everything in Pro for twelve months, two of them free."],
                ["A verified fact claim", "1 report", "Post a photo-backed claim; once another resident backs it with their own proof, a report is yours."],
              ].map(([n, price, d]) => (
                <div className="ld-menu-item" key={n}>
                  <dt>{n}</dt>
                  <dd className="ld-menu-price">{price}</dd>
                  <dd className="ld-menu-desc">{d}</dd>
                </div>
              ))}
            </dl>
          </section>

          <section className="ld-cta ld-reveal" aria-labelledby="cta-h">
            <h2 id="cta-h">Spend twenty minutes before you spend two crore.</h2>
            <Link to="/auth?mode=register" className="ld-button" data-testid="landing-cta-footer">
              Build my first report <ArrowRight size={16} />
            </Link>
          </section>
        </main>
      </div>

      <footer className="ld-footer">
        <img
          src="/assets/cubbon-park-bangalore-colonial-india.jpg"
          alt="An early twentieth-century postcard of Cubbon Park, Bangalore, with the public offices behind the lawns"
          width="1648" height="1029" loading="lazy" className="ld-footer-photo"
        />
        <div className="ld-footer-menu">
          <p className="ld-footer-name">localiq</p>
          <ul>
            <li><a href="#how">How it works</a></li>
            <li><a href="#measured">What it measures</a></li>
            <li><a href="#pricing">Pricing</a></li>
            <li><Link to="/auth">Sign in</Link></li>
            <li><Link to="/auth?mode=register">Create an account</Link></li>
          </ul>
          <p className="ld-footer-legal">
            Bengaluru only for now. Decision support, not advice. No listings, no brokerage.
          </p>
          <p className="ld-footer-credits">
            Pictures:{" "}
            {CREDITS.map(([t, by, lic, url], i) => (
              <span key={t}>
                <a href={url} target="_blank" rel="noreferrer">{t}</a> by {by}, {lic}
                {i < CREDITS.length - 1 ? "; " : "."}
              </span>
            ))}{" "}
            Via Wikimedia Commons.
          </p>
        </div>
      </footer>
    </div>
  );
}
