import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { ArrowUpRight, CarFront, Gauge, IndianRupee, LoaderCircle, Search, ShieldCheck, Sparkles, Users } from 'lucide-react';
import './styles.css';

const examples = [
  'A safe 7-seater SUV under 25 lakh, automatic',
  'Fuel-efficient city car with a sunroof under 15 lakh',
  'A cheaper alternative to the Toyota Fortuner for rough roads',
];

function App() {
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState('budget_fit');
  const [results, setResults] = useState([]);
  const [specialSuggestion, setSpecialSuggestion] = useState(null);
  const [parsed, setParsed] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  async function loadRecommendations(searchText, selectedSort) {
    if (!searchText.trim() || loading) return;
    setLoading(true); setError('');
    try {
      const response = await fetch('/recommend', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: searchText.trim(), sort_by: selectedSort }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Could not get recommendations.');
      setParsed(data.parsed_query); setResults(data.recommendations || []); setSpecialSuggestion(data.special_suggestion || null); setSortBy(data.sorted_by || selectedSort);
    } catch (err) {
      setError(err.message || 'Could not reach CarSense. Start the Flask API and try again.');
      setResults([]); setSpecialSuggestion(null);
    } finally { setLoading(false); }
  }

  function recommend(event) {
    event.preventDefault();
    loadRecommendations(query, sortBy);
  }

  function changeSort(event) {
    const nextSort = event.target.value;
    setSortBy(nextSort);
    if (query.trim() && results.length) loadRecommendations(query, nextSort);
  }

  return <main className="page-shell">
    <nav className="topbar"><a className="brand" href="#top"><span className="brand-mark"><CarFront size={19} /></span>carsense<span className="brand-dot">.</span></a><span className="nav-note"><span className="live-dot" /> AI vehicle finder</span></nav>
    <section className="hero" id="top">
      <div className="eyebrow"><Sparkles size={14} /> YOUR NEXT CAR, MADE PERSONAL</div>
      <h1>Find a car that<br /><em>fits your life.</em></h1>
      <p className="lede">Tell us what matters. CarSense searches Indian-market vehicles and finds the ones that make sense for you.</p>
      <form className="search-card" onSubmit={recommend}>
        <label htmlFor="car-query">What are you looking for?</label>
        <div className="input-row"><Search size={19} /><input id="car-query" value={query} onChange={e => setQuery(e.target.value)} placeholder="e.g. a safe family SUV under 20 lakh…" maxLength={600} /><button type="submit" disabled={loading || !query.trim()}>{loading ? <LoaderCircle className="spin" size={18} /> : <>Find my car <ArrowUpRight size={17} /></>}</button></div>
        <div className="examples"><span>TRY</span>{examples.map(item => <button type="button" key={item} onClick={() => setQuery(item)}>{item}</button>)}</div>
      </form>
      {error && <div className="error" role="alert">{error}</div>}
    </section>

    {results.length > 0 && <section className="results" aria-live="polite">
      <div className="results-heading"><div><div className="eyebrow">YOUR SHORTLIST</div><h2>Worth a closer look.</h2></div><span className="result-count">{results.length} MATCH{results.length === 1 ? '' : 'ES'}</span></div>
      <div className="sort-row"><label htmlFor="sort-by">Sort shortlist by</label><select id="sort-by" value={sortBy} onChange={changeSort} disabled={loading}>
        <option value="recommended">Best intent match</option>
        <option value="budget_fit" disabled={!parsed?.budget}>Closest to budget</option>
        <option value="price_low">Price: low to high</option>
        <option value="price_high">Price: high to low</option>
        <option value="seats">More seats</option>
        <option value="fuel_type">Fuel type</option>
        <option value="transmission">Transmission type</option>
        <option value="body_type">Body type</option>
        <option value="mileage">ARAI mileage</option>
        <option value="safety">Safety score</option>
        <option value="performance">Performance</option>
        <option value="comfort">Comfort & features</option>
        <option value="city">City driving</option>
        <option value="offroad">Off-road ability</option>
        <option value="boot_space">Boot space</option>
        <option value="ground_clearance">Ground clearance</option>
        <option value="ev_range">EV range</option>
        <option value="warranty">Warranty</option>
        <option value="resale">Resale rating</option>
      </select>{loading && <LoaderCircle className="spin sort-spinner" size={16} />}</div>
      <div className="car-grid">{results.map((car, i) => <article className="car-card" key={`${car.brand}-${car.model}`}>
        <div className="card-top"><span className="rank">0{i + 1}</span><span className="score">{i === 0 ? 'TOP MATCH' : 'SHORTLIST'}</span></div>
        <div className="car-name"><span>{car.brand}</span><h3>{car.model}</h3></div>
        <div className="price"><IndianRupee size={15} />{Number(car.price).toLocaleString('en-IN')}<small> starting ex-showroom</small></div>
        {car.capability_match != null && <div className="price-gap">{car.capability_match}% capability match vs {car.compared_with}</div>}
        {parsed?.budget && <div className="price-gap">{car.budget_difference === 0 ? 'At your budget' : `₹${Number(car.budget_difference).toLocaleString('en-IN')} below your budget`}{sortBy === 'budget_fit' ? ' · closest prices first' : ''}</div>}
        <div className="specs"><span><Users size={15} /> {car.seats} seats</span><span><CarFront size={15} /> {car.body_type}</span></div>
        <div className="card-foot"><span><ShieldCheck size={15} /> {car.fuel_type || 'Multiple fuels'}</span><span><Gauge size={15} /> {car.variant || 'Base variant'}</span></div>
      </article>)}</div>
      {specialSuggestion && <article className="special-card">
        <div className="special-kicker"><Sparkles size={14} /> BUDGET-FLEXIBLE PICK</div>
        <div className="special-content"><div><span className="special-brand">{specialSuggestion.brand}</span><h3>{specialSuggestion.model}</h3><div className="specs"><span><Users size={15} /> {specialSuggestion.seats} seats</span><span><CarFront size={15} /> {specialSuggestion.body_type}</span><span><ShieldCheck size={15} /> {specialSuggestion.fuel_type}</span></div></div>
          <div className="special-price"><b><IndianRupee size={15} />{Number(specialSuggestion.price).toLocaleString('en-IN')}</b><small>starting ex-showroom · {specialSuggestion.variant || 'base variant'}</small><span className={specialSuggestion.budget_relation === 'above' ? 'over-budget' : 'under-budget'}>{specialSuggestion.budget_relation === 'above' ? `₹${Number(specialSuggestion.budget_difference).toLocaleString('en-IN')} above budget` : specialSuggestion.budget_relation === 'at' ? 'At your budget' : `₹${Number(Math.abs(specialSuggestion.budget_difference)).toLocaleString('en-IN')} below budget`}</span></div></div>
      </article>}
      <p className="data-note">Prices and vehicle details come from the included catalog and may change. Confirm current specifications and pricing with a dealer.</p>
    </section>}

    {!results.length && !loading && <section className="how"><div className="how-item"><span>01</span><div><b>Say it naturally</b><p>Budget, space, fuel, or the way you drive.</p></div></div><div className="how-item"><span>02</span><div><b>We search the details</b><p>Semantic retrieval meets real vehicle specs.</p></div></div><div className="how-item"><span>03</span><div><b>Get a focused shortlist</b><p>Relevant options, ranked around your priorities.</p></div></div></section>}
    <footer><span>carsense<span className="brand-dot">.</span></span><span>Built for the roads ahead · India</span></footer>
  </main>;
}

createRoot(document.getElementById('root')).render(<App />);
