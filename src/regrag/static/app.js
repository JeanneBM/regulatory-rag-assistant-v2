"use strict";

const $ = (id) => document.getElementById(id);

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

function link(url, text) {
  const a = el("a", "source", text);
  if (url && url.startsWith("https://eur-lex.europa.eu/")) {
    a.href = url;
    a.target = "_blank";
    a.rel = "noopener noreferrer";
  }
  return a;
}

function claimCard(claim, rejected) {
  const card = el("article", rejected ? "claim rejected" : "claim");
  card.append(el("p", "statement", claim.statement));
  const meta = el("p", "meta");
  meta.append(link(claim.url, claim.citation));
  meta.append(el("span", `badge ${claim.support}`, claim.support));
  card.append(meta);
  if (claim.support_note) card.append(el("p", "note", claim.support_note));
  card.append(el("blockquote", "quote", claim.quote));
  return card;
}

function render(result) {
  const labels = {
    answered: "Answer",
    insufficient_evidence: "Not enough evidence to answer",
    retrieval_only: "Evidence only (generation is not configured)",
  };
  $("status").replaceChildren(el("h2", `status ${result.status}`, labels[result.status] || result.status));
  if (result.abstention_reason) $("status").append(el("p", "reason", result.abstention_reason));

  $("claims").replaceChildren(...result.claims.map((c) => claimCard(c, false)));

  $("rejected-box").hidden = result.rejected_claims.length === 0;
  $("rejected").replaceChildren(...result.rejected_claims.map((c) => claimCard(c, true)));

  $("evidence-box").hidden = result.evidence.length === 0;
  $("evidence-box").open = result.status === "retrieval_only";
  $("evidence").replaceChildren(...result.evidence.map((e) => {
    const item = el("article", "evidence");
    const head = el("p", "meta");
    head.append(link(e.url, e.citation));
    const score = e.reranker_score ?? e.score;
    if (typeof score === "number") head.append(el("span", "score", `score ${score.toFixed(3)}`));
    item.append(head);
    if (e.article_title) item.append(el("p", "title", e.article_title));
    item.append(el("blockquote", "quote", e.text));
    return item;
  }));
}

async function ask(event) {
  event.preventDefault();
  const question = $("question").value.trim();
  if (question.length < 3) return;
  $("submit").disabled = true;
  $("status").replaceChildren(el("p", "pending", "Searching the acts..."));
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, act: $("act").value || null }),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || `HTTP ${response.status}`);
    render(body);
  } catch (error) {
    $("status").replaceChildren(el("p", "error", `Request failed: ${error.message}`));
    $("claims").replaceChildren();
  } finally {
    $("submit").disabled = false;
  }
}

async function loadInfo() {
  try {
    const info = await (await fetch("/api/info")).json();
    const corpus = info.corpus || {};
    const parts = [`Backend: ${info.backend}`, `verification: ${info.verification}`];
    if (corpus.fetched_at) parts.push(`sources fetched ${corpus.fetched_at.slice(0, 10)}`);
    if (corpus.corpus_sha256) parts.push(`corpus ${corpus.corpus_sha256.slice(0, 12)}`);
    $("corpus").textContent = parts.join(" · ");
  } catch (_) {
    $("corpus").textContent = "";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  $("ask-form").addEventListener("submit", ask);
  loadInfo();
});
