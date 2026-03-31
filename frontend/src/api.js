const API = '/api/v1';

export async function fetchProjects(vertical = null) {
  const url = vertical ? `${API}/infra/projects?vertical=${vertical}` : `${API}/infra/projects`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchProject(id) {
  const res = await fetch(`${API}/infra/projects/${id}`);
  return res.json();
}

export async function fetchSolutions(vertical = null) {
  const url = vertical ? `${API}/marketplace/solutions?vertical=${vertical}` : `${API}/marketplace/solutions`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchMarketplaceStats() {
  const res = await fetch(`${API}/marketplace/marketplace/stats`);
  return res.json();
}

export async function fetchImpactDashboard(vertical = null) {
  const url = vertical ? `${API}/impact/impact/dashboard?vertical=${vertical}` : `${API}/impact/impact/dashboard`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchVerticalSummary() {
  const res = await fetch(`${API}/infra/verticals/summary`);
  return res.json();
}

export async function fetchTreasury() {
  const res = await fetch(`${API}/dao/treasury`);
  return res.json();
}

export async function runCalculator(vertical, endpoint, data) {
  const res = await fetch(`${API}/infra/calc/${vertical}/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  return res.json();
}

export async function seedData() {
  const res = await fetch(`${API}/infra/seed`, { method: 'POST' });
  return res.json();
}
