# PharmaGuard – Pharmacogenomic Risk Prediction System

> **Pharmacogenomics / Explainable AI System**

[![Live Demo](https://img.shields.io/badge/Live%20Demo-Vercel-black?logo=vercel)](https://pharmaguard.vercel.app)
[![LinkedIn Video](https://img.shields.io/badge/Demo%20Video-LinkedIn-blue?logo=linkedin)](https://linkedin.com/in/your-profile)
[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js)](https://nextjs.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-green?logo=fastapi)](https://fastapi.tiangolo.com)

---

## 🧬 Overview

**PharmaGuard** is a production-ready pharmacogenomic risk prediction system that parses **VCF v4.2** files, identifies variants in 6 critical pharmacogenes, applies **CPIC-aligned deterministic rules**, and generates **explainable AI** drug safety assessments. The system outputs a strict, validated JSON schema.

### Key Differentiators
- 🎯 **Deterministic risk engine** — LLM only *explains*, never decides risk
- 📋 **CPIC v2.0 aligned** — Clinical Pharmacogenetics Implementation Consortium guidelines
- 🔒 **No genomic data storage** — in-memory processing only
- 📊 **CSV knowledge base** — interpretable, auditable rule source
- 🏗️ **Production architecture** — Docker, Vercel, Render deployment ready

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     USER (Browser)                       │
│              Next.js Frontend (Port 3000)                │
│  VCF Upload → Drug Select → Risk Display → JSON Viewer  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP POST /api/analyze
                       ▼
┌─────────────────────────────────────────────────────────┐
│              Node.js Backend (Port 3001)                 │
│    Express • CORS • Rate Limiting • Helmet Security      │
└──────────────────────┬──────────────────────────────────┘
                       │ multipart/form-data proxy
                       ▼
┌─────────────────────────────────────────────────────────┐
│         Python FastAPI Genomics Service (Port 8000)      │
│                                                          │
│  vcf_parser.py  →  risk_engine.py  →  llm_service.py   │
│  (cyvcf2/manual)   (CSV rules)       (OpenAI API)       │
│                          │                              │
│              pharmacogenomic_rules.csv                  │
│              (6 genes × 6 drugs × 46 rules)             │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Supported Genes & Drugs

| Gene | Drug | Key Variants |
|------|------|--------------|
| CYP2D6 | CODEINE | *4, *5, *1xN |
| CYP2C19 | CLOPIDOGREL | *2, *3, *17 |
| CYP2C9 | WARFARIN | *2, *3 |
| SLCO1B1 | SIMVASTATIN | *5, *15 |
| TPMT | AZATHIOPRINE | *3A, *3B, *3C, *2 |
| DPYD | FLUOROURACIL | *2A, *13, rs3918290 |

---

## 🚀 Installation & Setup

### Prerequisites
- Node.js 18+
- Python 3.11+
- pip
- npm

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/pharmaguard.git
cd pharmaguard
cp .env.example .env
# Edit .env with your OPENAI_API_KEY
```

### 2. Python Genomics Service

```bash
cd genomics-service-python
pip install -r requirements.txt
python main.py
# → Running at http://localhost:8000
# → API docs at http://localhost:8000/docs
```

> **Note**: `cyvcf2` requires C build tools. If installation fails, the service uses a built-in manual VCF parser as fallback.

### 3. Node.js Backend

```bash
cd backend-node
npm install
npm run dev
# → Running at http://localhost:3001
```

### 4. Next.js Frontend

```bash
cd frontend
npm install
npm run dev
# → Running at http://localhost:3000
```

### 5. Open Application

Navigate to [http://localhost:3000](http://localhost:3000)

---

## 📁 Project Structure

```
rift2/
├── frontend/                      # Next.js App Router frontend
│   ├── app/
│   │   ├── layout.tsx            # Root layout with metadata
│   │   ├── page.tsx              # Main analysis page
│   │   └── globals.css           # Global styles with glassmorphism
│   ├── components/
│   │   ├── VcfUpload.tsx         # Drag-and-drop VCF uploader
│   │   ├── RiskCard.tsx          # Color-coded risk display card
│   │   ├── JsonViewer.tsx        # Syntax-highlighted JSON viewer
│   │   └── ErrorPanel.tsx        # Structured error display
│   └── lib/
│       └── types.ts              # TypeScript types (strict schema)
│
├── backend-node/                  # Express proxy/orchestration
│   ├── server.js                 # Main Express server
│   ├── package.json
│   └── Dockerfile
│
├── genomics-service-python/       # FastAPI genomics microservice
│   ├── main.py                   # FastAPI app & endpoints
│   ├── vcf_parser.py             # cyvcf2 VCF parser
│   ├── risk_engine.py            # Deterministic CPIC rule engine
│   ├── llm_service.py            # OpenAI explanation generator
│   ├── models.py                 # Pydantic strict schema models
│   ├── requirements.txt
│   └── Dockerfile
│
├── data/
│   └── pharmacogenomic_rules.csv # CPIC knowledge base (46 rules)
│
├── sample_vcfs/
│   ├── sample1_cyp2d6_pm.vcf    # CYP2D6 PM patient (9 variants)
│   └── sample2_dpyd_toxic.vcf   # DPYD *2A het patient (8 variants)
│
├── tests/
│   ├── test_risk_engine.py       # Pytest unit tests (15 tests)
│   ├── expected_output_sample1.json
│   └── expected_output_sample2.json
│
├── .env.example                  # Environment variables template
└── README.md
```

---

## 📡 API Documentation

### POST `/api/analyze` (Node Backend)

**Request**: `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `vcf_file` | File | ✅ | VCF v4.2 file |
| `drugs` | string | ✅ | Comma-separated drug names |
| `patient_id` | string | ❌ | Patient identifier |

**Response**: `application/json`

```json
{
  "success": true,
  "request_id": "uuid",
  "results": [...],
  "total_drugs_analyzed": 2,
  "timestamp": "ISO8601"
}
```

### POST `/analyze` (Python Service direct)

| Field | Type | Description |
|-------|------|-------------|
| `vcf_file` | File | VCF v4.2 file |
| `drugs` | string | Comma-separated |
| `patient_id` | string | Optional |

---

## 📊 JSON Schema

```json
{
  "patient_id": "PATIENT_XXX",
  "drug": "DRUG_NAME",
  "timestamp": "ISO8601",
  "risk_assessment": {
    "risk_label": "Safe|Adjust Dosage|Toxic|Ineffective|Unknown",
    "confidence_score": 0.0,
    "severity": "none|low|moderate|high|critical"
  },
  "pharmacogenomic_profile": {
    "primary_gene": "GENE",
    "diplotype": "*X/*Y",
    "phenotype": "PM|IM|NM|RM|URM|Unknown",
    "detected_variants": [{"rsid": "...", "chromosome": "...", "position": 0}]
  },
  "clinical_recommendation": {
    "cpic_guideline": "...",
    "dose_adjustment": "...",
    "alternative_drugs": ["..."]
  },
  "llm_generated_explanation": {
    "summary": "...",
    "mechanism": "...",
    "variant_citations": ["rsXXXX"]
  },
  "quality_metrics": {
    "vcf_parsing_success": true,
    "guideline_version": "CPIC v2.0",
    "llm_confidence": 0.0
  }
}
```

---

## 🔬 Risk Engine Logic

Risk is determined **deterministically** using `pharmacogenomic_rules.csv`:

1. **Diplotype exact match** → lookup phenotype + risk from CSV
2. **Phenotype match** → lookup risk from CSV
3. **rsID special cases** → DPYD toxic variant detection
4. **Unknown fallback** → unknown risk with monitoring recommendation

**LLM (GPT-4) only explains the pre-determined risk** — it never modifies risk_label, phenotype, or confidence_score.

---

## 🧪 Running Tests

```bash
cd tests
pip install pytest
pytest test_risk_engine.py -v
```

Expected: **15 tests passing**

---

## 🐳 Docker Deployment

```bash
# Python service
cd genomics-service-python
docker build -t pharmaguard-python .
docker run -p 8000:8000 --env-file ../.env pharmaguard-python

# Node backend
cd backend-node
docker build -t pharmaguard-node .
docker run -p 3001:3001 --env-file ../.env pharmaguard-node
```

---

## ☁️ Cloud Deployment

### Vercel (Frontend)
```bash
cd frontend
npx vercel --prod
# Set NEXT_PUBLIC_API_URL=https://pharmaguard-node.onrender.com
```

### Render (Backend Services)
1. Create two **Web Services** on [render.com](https://render.com)
2. Python service: Root dir = `genomics-service-python`, Start = `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Node service: Root dir = `backend-node`, Start = `node server.js`
4. Set environment variables from `.env.example`

---

## 🔒 Security

- ✅ No genomic data stored — all processing in-memory
- ✅ Rate limiting (100 req/15min)
- ✅ Helmet.js security headers
- ✅ CORS configured
- ✅ File size limits (50MB)
- ✅ VCF header validation

## 📄 License

MIT License — see LICENSE file for details.
