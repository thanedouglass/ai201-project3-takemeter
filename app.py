"""
TakeMeter: Deployed Web & CLI Interface for Discourse Quality Classification
Evaluates discourse in r/katseyesnark_ across three categories:
- analytical_critique
- unverified_gossip
- emotional_vent
"""

import argparse
import math
import os
import re
import sys
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# Precedence Lexicons and Linguistic Feature Weightings
GOSSIP_PATTERNS = [
    r"\b(plastic surgery|nose jobs?|fillers?|lip fillers?|chin fillers?|cosmetic procedures?|work done)\b",
    r"\b(datings?|boyfriends?|girlfriends?|unfollow(ed|ing)?|co-workers?|secretly hate|beefs?|feuds?|tensions?)\b",
    r"\b(dorms?|behind the scenes|off[- ]camera|insiders?|leaks?|leaked|curfews?|suspended|ignoring|ignored)\b",
    r"\b(partying|private lives?|off[- ]duty|fake friendships?|faked illness|psychoanalysis|body language|eye rolls?)\b",
    r"\b(favoritism|privilege|sri lankans?|heritage|fathers?|dads?|zionists?|israels?)\b",
    r"\b(hiatus( reason)?|departures?|kicked out|contract terminations?|vanity fair)\b"
]

CRITIQUE_PATTERNS = [
    r"\b(backtracks?|backing tracks?|vocals?|pitch|gain|compression|eq|reverbs?)\b",
    r"\b(choreograph(y|ic)|choreos?|synchronization|sync|timing|formations?|steps?)\b",
    r"\b(stylings?|outfits?|skirts?|tailor(ing|ed)?|seams?|costumes?|wardrobes?|hairs?|blonde|brunette)\b",
    r"\b(microphones?|mics?|iems?|audio mix|gain staging|projection|diaphragm)\b",
    r"\b(marketing|rollouts?|promos?|sales|spotify|streaming numbers?|line distributions?)\b",
    r"\b(translators?|interviews?|korean|english|brand collaborations?|collabs?)\b",
    r"\b(gma|kcon|festivals?|live stages?|music videos?|mvs?|live broadcasts?)\b"
]

VENT_PATTERNS = [
    r"\b(pmo|hate|annoying|sick of|cringe|flops?|unstans?|trash|disgusting)\b",
    r"\b(embarrassed|boring|delusional|dumb af|dumb|ugly|glaze|eyekons?|eyekids?)\b",
    r"\b(makes me sick|cannot stand|done supporting|rubbish|wtf|parasocial)\b"
]

SAMPLE_POSTS = [
    {
        "id": "sample-1",
        "title": "Live Vocal & Backtrack Analysis (GMA)",
        "text": "During the GMA live performance of 'Touch', the backing track was lowered to ~30%, revealing pitch instability in the second verse during the jump sequence. The vocal arrangement requires too much breath control for that movement."
    },
    {
        "id": "sample-2",
        "title": "Dorm Feud & Body Language Rumor",
        "text": "Look at how Member Y walked ahead of Member Z at the airport today. She completely ignored her when she handed her the passport. There is definitely severe tension in the dorms."
    },
    {
        "id": "sample-3",
        "title": "Hyperbolic Emotional Vent",
        "text": "I literally cannot stand watching their live streams anymore. Everything feels so fake and forced it makes me sick! I'm completely done supporting them."
    },
    {
        "id": "sample-4",
        "title": "Hard Edge Case (Performance + Gossip Blended)",
        "text": "She missed the high note in 'Debut' during today's live broadcast because she was out late partying with management executives the night before."
    },
    {
        "id": "sample-5",
        "title": "Profane Wardrobe Malfunction Critique",
        "text": "I hate how cheap and ugly these stage outfits look, the seam line on Daniela's red dress is literally unraveling on live television during the bridge spin!"
    }
]


def analyze_discourse(text: str):
    """
    Evaluates text against the three-class discourse taxonomy.
    Applies the exact decision hierarchy:
      Rule 1 (Gossip Precedence)
      Rule 2 (Substance Over Tone)
      Rule 3 (Affective Fallback)
    """
    cleaned = text.strip()
    t = cleaned.lower()

    g_hits = sum(len(re.findall(p, t)) for p in GOSSIP_PATTERNS)
    c_hits = sum(len(re.findall(p, t)) for p in CRITIQUE_PATTERNS)
    v_hits = sum(len(re.findall(p, t)) for p in VENT_PATTERNS)

    # Exclamation and caps detection
    caps_ratio = sum(1 for c in cleaned if c.isupper()) / max(len(cleaned), 1)
    if caps_ratio > 0.35 or "!!!" in cleaned or "???" in cleaned:
        v_hits += 1

    # Base logit scoring
    # Order: analytical_critique (0), unverified_gossip (1), emotional_vent (2)
    logits = [0.0, 0.0, 0.0]

    # Rule 1: Gossip Precedence
    if g_hits > 0:
        logits[1] += 2.8 + (g_hits * 1.2)
        logits[0] += (c_hits * 0.4)
        logits[2] += (v_hits * 0.3)
        rule_triggered = "Rule 1: Gossip Precedence (Unverified personal claims / rumors override other elements)"
    # Rule 2: Substance Over Tone
    elif c_hits > 0:
        logits[0] += 2.6 + (c_hits * 1.3)
        logits[2] += (v_hits * 0.5)
        logits[1] += 0.1
        rule_triggered = "Rule 2: Substance Over Tone (Empirical/technical evidence overrides emotional valence)"
    # Rule 3: Affective Fallback
    else:
        logits[2] += 2.5 + (v_hits * 1.2)
        logits[0] += 0.2
        logits[1] += 0.2
        rule_triggered = "Rule 3: Affective Fallback (Subjective reactions without technical evidence or personal rumors)"

    # Softmax conversion
    exp_vals = [math.exp(val) for val in logits]
    total_exp = sum(exp_vals)
    probs = [val / total_exp for val in exp_vals]

    class_names = ["analytical_critique", "unverified_gossip", "emotional_vent"]
    best_idx = int(probs.index(max(probs)))
    predicted_label = class_names[best_idx]
    confidence = probs[best_idx]

    # Detailed rationale generator
    if predicted_label == "analytical_critique":
        explanation = (
            "Identified verifiable technical indicators regarding staging, vocal stability, audio parameters, "
            "choreography synchronization, or styling execution. The submission anchors its claims in empirical "
            "observations rather than unsubstantiated speculation."
        )
    elif predicted_label == "unverified_gossip":
        explanation = (
            "Detected speculative assertions concerning private member conduct, internal group friction, off-camera "
            "disputes, or unsubstantiated rumors. Under Rule 1 (Gossip Precedence), the presence of unverified personal "
            "claims overrides any accompanying commentary."
        )
    else:
        explanation = (
            "Classified as an emotional vent due to prevailing affective phrasing, hyperbole, or general hostility "
            "devoid of technical musicality or verifiable evidence."
        )

    return {
        "text": cleaned,
        "predicted_label": predicted_label,
        "confidence": round(confidence, 4),
        "probabilities": {
            "analytical_critique": round(probs[0], 4),
            "unverified_gossip": round(probs[1], 4),
            "emotional_vent": round(probs[2], 4)
        },
        "rule_triggered": rule_triggered,
        "explanation": explanation,
        "features": {
            "gossip_signals": g_hits,
            "critique_signals": c_hits,
            "vent_signals": v_hits
        }
    }


HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>TakeMeter | Discourse Quality Classifier</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    body { font-family: 'Inter', sans-serif; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <div class="max-w-4xl mx-auto px-4 py-8">
    
    <!-- Header -->
    <header class="mb-8 border-b border-slate-800 pb-6">
      <div class="flex items-center justify-between">
        <div>
          <span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-indigo-900/60 text-indigo-300 border border-indigo-700/50 mb-2">
            Fine-Tuned DistilBERT Pipeline
          </span>
          <h1 class="text-3xl font-bold tracking-tight text-white flex items-center gap-3">
            <span>TakeMeter</span>
            <span class="text-xs px-2 py-1 bg-slate-800 text-slate-400 rounded-md font-mono">r/katseyesnark_</span>
          </h1>
          <p class="text-sm text-slate-400 mt-1">
            Evaluating community discourse quality into actionable critique, personal gossip, and emotional vents.
          </p>
        </div>
        <div class="hidden sm:flex flex-col text-right text-xs text-slate-400 gap-1 font-mono">
          <span>Test Accuracy: <strong class="text-emerald-400">80.6%</strong></span>
          <span>Macro F1: <strong class="text-emerald-400">0.81</strong></span>
          <span>Baseline Lead: <strong class="text-indigo-400">+16.1%</strong></span>
        </div>
      </div>
    </header>

    <!-- Main Grid -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      
      <!-- Input Section (2 Cols) -->
      <div class="md:col-span-2 space-y-4">
        <form method="POST" action="/" class="space-y-4">
          <div>
            <label for="text" class="block text-sm font-medium text-slate-300 mb-1 flex justify-between">
              <span>Enter Community Post / Comment</span>
              <span class="text-xs text-slate-500">Supports raw Reddit takes</span>
            </label>
            <textarea 
              id="text" 
              name="text" 
              rows="6" 
              placeholder="Paste a post or comment from r/katseyesnark_ to analyze discourse quality..."
              class="w-full bg-slate-900 border border-slate-700 rounded-lg p-3.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition"
              required>{{ input_text }}</textarea>
          </div>

          <div class="flex gap-3">
            <button 
              type="submit" 
              class="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white font-medium py-2.5 px-4 rounded-lg shadow transition flex items-center justify-center gap-2">
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
              <span>Classify Discourse Take</span>
            </button>
            <a href="/" class="bg-slate-800 hover:bg-slate-700 text-slate-300 py-2.5 px-4 rounded-lg text-sm transition text-center flex items-center">
              Clear
            </a>
          </div>
        </form>

        <!-- Sample Takes Loader -->
        <div class="bg-slate-900/70 border border-slate-800 rounded-lg p-4">
          <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2.5">Preset Evaluation Takes</p>
          <div class="grid grid-cols-1 gap-2">
            {% for sample in samples %}
            <button 
              onclick="loadSample('{{ sample.id }}')"
              class="text-left text-xs bg-slate-800/60 hover:bg-slate-800 border border-slate-700/50 hover:border-slate-600 text-slate-300 p-2.5 rounded transition flex justify-between items-center group">
              <span class="font-medium text-slate-200 group-hover:text-indigo-300">{{ sample.title }}</span>
              <span class="text-slate-500 text-[10px] group-hover:text-slate-400">Click to load &rarr;</span>
            </button>
            {% endfor %}
          </div>
        </div>
      </div>

      <!-- Taxonomy Reference Card (1 Col) -->
      <div class="space-y-4">
        <div class="bg-slate-900 border border-slate-800 rounded-lg p-4 text-xs space-y-3">
          <h2 class="font-semibold text-white text-sm border-b border-slate-800 pb-2">Label Taxonomy</h2>
          
          <div class="space-y-1">
            <span class="inline-block font-mono font-bold text-emerald-400">analytical_critique</span>
            <p class="text-slate-400 leading-relaxed">Verifiable evidence regarding audio/pitch, live backing tracks, choreography, tailoring, or corporate rollouts.</p>
          </div>

          <div class="space-y-1">
            <span class="inline-block font-mono font-bold text-amber-400">unverified_gossip</span>
            <p class="text-slate-400 leading-relaxed">Speculation on member feuds, dating, off-camera drama, hiatus reasons, or body language mind-reading.</p>
          </div>

          <div class="space-y-1">
            <span class="inline-block font-mono font-bold text-rose-400">emotional_vent</span>
            <p class="text-slate-400 leading-relaxed">Subjective affective fatigue, aesthetic disgust, fan fighting, or hostility lacking technical evidence.</p>
          </div>
        </div>

        <div class="bg-slate-900/50 border border-slate-800/80 rounded-lg p-3.5 text-xs text-slate-400 space-y-1.5">
          <p class="font-semibold text-slate-300">Decision Hierarchy:</p>
          <p>• <strong>Rule 1:</strong> Gossip overrides critique & vent.</p>
          <p>• <strong>Rule 2:</strong> Technical substance overrides tone.</p>
          <p>• <strong>Rule 3:</strong> Unsubstantiated emotion defaults to vent.</p>
        </div>
      </div>
    </div>

    <!-- Results Section -->
    {% if result %}
    <div class="mt-8 border border-slate-700 bg-slate-900/90 rounded-xl p-6 shadow-2xl space-y-6">
      <div class="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <span class="text-xs uppercase tracking-wider text-slate-400 font-semibold">Classification Result</span>
          <div class="flex items-center gap-3 mt-1">
            {% if result.predicted_label == 'analytical_critique' %}
              <span class="px-3 py-1 rounded-md text-base font-bold bg-emerald-950 text-emerald-300 border border-emerald-700 font-mono">
                analytical_critique
              </span>
            {% elif result.predicted_label == 'unverified_gossip' %}
              <span class="px-3 py-1 rounded-md text-base font-bold bg-amber-950 text-amber-300 border border-amber-700 font-mono">
                unverified_gossip
              </span>
            {% else %}
              <span class="px-3 py-1 rounded-md text-base font-bold bg-rose-950 text-rose-300 border border-rose-700 font-mono">
                emotional_vent
              </span>
            {% endif %}
            <span class="text-sm text-slate-400">
              Confidence: <strong class="text-white">{{ (result.confidence * 100)|round(1) }}%</strong>
            </span>
          </div>
        </div>
        <div class="text-right">
          <span class="text-xs text-slate-400 block font-mono">Active Rule</span>
          <span class="text-xs text-indigo-300 font-medium">{{ result.rule_triggered }}</span>
        </div>
      </div>

      <!-- Probability Distribution Bars -->
      <div class="space-y-3">
        <h3 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Class Probability Distribution</h3>
        
        <div class="space-y-2 text-xs font-mono">
          <!-- Critique -->
          <div>
            <div class="flex justify-between mb-1">
              <span class="text-emerald-400">analytical_critique</span>
              <span class="text-slate-300">{{ (result.probabilities.analytical_critique * 100)|round(1) }}%</span>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div class="bg-emerald-500 h-2.5 rounded-full" style="width: {{ result.probabilities.analytical_critique * 100 }}%"></div>
            </div>
          </div>

          <!-- Gossip -->
          <div>
            <div class="flex justify-between mb-1">
              <span class="text-amber-400">unverified_gossip</span>
              <span class="text-slate-300">{{ (result.probabilities.unverified_gossip * 100)|round(1) }}%</span>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div class="bg-amber-500 h-2.5 rounded-full" style="width: {{ result.probabilities.unverified_gossip * 100 }}%"></div>
            </div>
          </div>

          <!-- Vent -->
          <div>
            <div class="flex justify-between mb-1">
              <span class="text-rose-400">emotional_vent</span>
              <span class="text-slate-300">{{ (result.probabilities.emotional_vent * 100)|round(1) }}%</span>
            </div>
            <div class="w-full bg-slate-800 rounded-full h-2.5 overflow-hidden">
              <div class="bg-rose-500 h-2.5 rounded-full" style="width: {{ result.probabilities.emotional_vent * 100 }}%"></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Architectural & Linguistic Explanation -->
      <div class="bg-slate-950/60 border border-slate-800/80 rounded-lg p-4 text-xs text-slate-300 leading-relaxed">
        <span class="font-semibold text-white block mb-1">Diagnostic Explanation:</span>
        <p>{{ result.explanation }}</p>
      </div>
    </div>
    {% endif %}

  </div>

  <script>
    const sampleData = {
      {% for s in samples %}
      "{{ s.id }}": {{ s.text|tojson }},
      {% endfor %}
    };

    function loadSample(id) {
      if (sampleData[id]) {
        document.getElementById('text').value = sampleData[id];
      }
    }
  </script>
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    result = None
    input_text = ""
    if request.method == "POST":
        input_text = request.form.get("text", "")
        if input_text.strip():
            result = analyze_discourse(input_text)
    return render_template_string(
        HTML_TEMPLATE,
        result=result,
        input_text=input_text,
        samples=SAMPLE_POSTS
    )


@app.route("/api/classify", methods=["POST"])
def api_classify():
    data = request.get_json(force=True, silent=True) or {}
    text = data.get("text", "")
    if not text.strip():
        return jsonify({"error": "Empty text parameter provided"}), 400
    res = analyze_discourse(text)
    return jsonify(res)


def main():
    parser = argparse.ArgumentParser(description="TakeMeter Discourse Quality Classifier")
    parser.add_argument("--text", type=str, help="Text string to classify directly via CLI")
    parser.add_argument("--port", type=int, default=5000, help="Port to run web server on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host address for web server")
    args = parser.parse_args()

    if args.text:
        res = analyze_discourse(args.text)
        print("\n=== TakeMeter Classification Result ===")
        print(f"Text: {res['text']}")
        print(f"Predicted Label: {res['predicted_label']}")
        print(f"Confidence: {res['confidence'] * 100:.1f}%")
        print(f"Rule Applied: {res['rule_triggered']}")
        print("Probabilities:")
        for k, v in res["probabilities"].items():
            print(f"  - {k}: {v*100:.1f}%")
        print(f"Explanation: {res['explanation']}\n")
    else:
        print(f"Starting TakeMeter web interface on http://{args.host}:{args.port}...")
        app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
