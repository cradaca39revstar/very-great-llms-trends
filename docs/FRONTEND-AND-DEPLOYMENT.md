# Frontend & Deployment Guide

## LLM Trending Products – Chatbot UI

**Version:** 1.0.0  
**Last Updated:** February 4, 2026  
**Audience:** Client handoff, Frontend developers, DevOps

---

## Related Documentation

- [LLM Trending Products Architecture](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) – Backend, API, and data flow
- [Terraform README (LLM)](../terraform/README-LLM.md) – Infrastructure and Lambda deployment
- [Frontend README](../frontend/README.md) – Quick reference in repo

---

## Table of Contents

1. [Overview](#overview)
2. [Tech Stack](#tech-stack)
3. [Application Structure](#application-structure)
4. [Environment Variables](#environment-variables)
5. [Local Development](#local-development)
6. [Build](#build)
7. [Deploy to AWS Amplify Hosting](#deploy-to-aws-amplify-hosting)
8. [Handoff & Demo Checklist](#handoff--demo-checklist)
9. [Troubleshooting](#troubleshooting)

---

## Overview

The **Trending Products** frontend is a single-page application (SPA) that:

- Authenticates users with **AWS Cognito** (same User Pool and App Client as the backend).
- Sends natural language queries to the **LLM API** (`POST /trending-products/query`) with the user’s JWT.
- Displays the generated report (top 5 products, brand, images, URLs, trends) and a **Download PDF** link when available.

The backend (API Gateway + Lambda) performs query parsing, Athena data retrieval, optional **Scraper Lambda (web search)** enrichment, Bedrock AI, and PDF generation. The frontend only calls the single REST endpoint and renders the response.

---

## Tech Stack

| Layer        | Technology                          |
| ------------ | ------------------------------------ |
| Build        | Vite                                 |
| Framework    | React 18 + TypeScript                |
| Routing      | react-router-dom                     |
| Auth         | AWS Amplify v6 (Cognito only)        |
| Styling      | CSS (index.css + BEM-style classes) |
| API          | Fetch to API Gateway URL             |

---

## Application Structure

```
frontend/
├── index.html
├── package.json
├── vite.config.ts
├── tsconfig.json
├── .env.example          # Template for env vars (do not commit .env.local)
├── public/
│   └── VG_Logo_White.webp
└── src/
    ├── main.tsx
    ├── App.tsx            # Router, protected/public routes, auth check
    ├── index.css          # Global styles
    ├── aws-config.ts      # Amplify.configure(Cognito) from VITE_* env
    ├── services/
    │   └── api.ts         # queryTrendingProducts(idToken, query)
    ├── types/
    │   └── api.ts         # TrendQueryResponse, Report, ReportProduct, SUPPORTED_L2_CATEGORIES
    └── pages/
        ├── LoginPage.tsx  # Email/password login, new-password challenge
        └── ChatPage.tsx   # Query input, category selector, report display, PDF link
```

### Key Flows

- **Login**: User enters email/password → Amplify `signIn` → Cognito. If backend returns `NEW_PASSWORD_REQUIRED`, the UI shows “New password required” and calls `confirmSignIn` with the new password.
- **Chat**: User types a query (e.g. “What are the top trending products in Skincare?”) or picks an L2 category from the dropdown → “Get report” → `fetchAuthSession()` for IdToken → `queryTrendingProducts(token, query)` → POST to `VITE_API_URL` with `Authorization: Bearer <token>` and `{ "query": "…" }`. Success: show report (products, request_id, execution_time_ms, product_count) and “Download PDF” if `pdf_url` is present. Error: show `message`, `request_id`, and `supported_categories` when provided.

---

## Environment Variables

All variables are prefixed with `VITE_` so Vite embeds them at build time. Set them in:

- **Local**: `frontend/.env.local` (copy from `frontend/.env.example`). Do **not** commit `.env.local`.
- **Amplify**: Build settings → Environment variables.

| Variable                     | Description                                      | Source (Terraform)                          |
| ---------------------------- | ------------------------------------------------ | ------------------------------------------- |
| `VITE_COGNITO_USER_POOL_ID`  | Cognito User Pool ID                             | `terraform output -raw cognito_user_pool_id` |
| `VITE_COGNITO_CLIENT_ID`     | Cognito App Client ID                            | `terraform output -raw cognito_client_id`   |
| `VITE_AWS_REGION`            | AWS region (same as API Gateway)                 | e.g. `us-east-1`                            |
| `VITE_API_URL`               | Full API Gateway URL including path              | `terraform output -raw api_gateway_url`     |

**Example `api_gateway_url`:**  
`https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/poc/trending-products/query`

Without Terraform: get **User Pool ID** and **Client ID** from AWS Console → Cognito → User pools → your pool → App integration → App client list. Get **API URL** from API Gateway → Stages → Invoke URL + resource path.

---

## Local Development

### Prerequisites

- Node.js 18+
- npm (or yarn/pnpm)
- Backend deployed: Terraform applied, Lambda (and optional Scraper) deployed, Cognito test user created (see [terraform/README-LLM.md](../terraform/README-LLM.md)).

### Steps

```bash
cd frontend
cp .env.example .env.local
# Edit .env.local with Cognito and API values (e.g. from terraform output)
npm install
npm run dev
```

Open the URL shown (e.g. `http://localhost:5173`). Sign in with the Cognito test user (e.g. `verygreat@test.com` / `VeryGreat123!`), then run a query (e.g. “What are the top trending products in Skincare?”).

---

## Build

```bash
cd frontend
npm install
npm run build
```

Output is in `frontend/dist/`. This directory is what you deploy to Amplify (or any static host).

---

## Deploy to AWS Amplify Hosting

For a full step-by-step guide including repository URL and branch (`amplify_versio`), see **[AMPLIFY-CLIENT-LINK.md](AMPLIFY-CLIENT-LINK.md)**.

### 1. Connect Repository

1. Push the repo (including the `frontend/` folder) to GitHub, GitLab, Bitbucket, or CodeCommit.
2. In **AWS Amplify Console** → **New app** → **Host web app** → connect the repo and branch (e.g. [very-great-llms-trends](https://github.com/cradaca39revstar/very-great-llms-trends), branch `amplify_versio`).

### 2. Build Settings

- **App root**: `frontend` (if the app lives in the `frontend/` directory).
- **Build command**: `npm run build` (or the value in `frontend/package.json`).
- **Output directory**: `dist` (Vite default).

### 3. Environment Variables

In Amplify → **App settings** → **Environment variables**, add:

| Name                         | Value (example) |
| ---------------------------- | ----------------- |
| `VITE_COGNITO_USER_POOL_ID`  | `us-east-1_xxxxx` |
| `VITE_COGNITO_CLIENT_ID`     | `xxxxxxxxxxxx`   |
| `VITE_AWS_REGION`            | `us-east-1`      |
| `VITE_API_URL`               | `https://...execute-api.us-east-1.amazonaws.com/poc/trending-products/query` |

Use the same values as the backend (same Cognito pool and API Gateway URL).

### 4. Save and Deploy

Save and run the build. The URL Amplify provides (e.g. `https://main.xxxxx.amplifyapp.com`) is where users sign in and run trending-product queries.

### 5. CORS

API Gateway must allow the Amplify origin. The Terraform for the LLM system typically configures CORS for the API; if you use a custom domain for the frontend, add that origin to the API Gateway CORS settings.

---

## Handoff & Demo Checklist

Use this for the client handoff and to ensure the frontend and full flow are demo-ready.

### Before the Demo

- [ ] **Backend**: Terraform applied; Orchestrator Lambda deployed; optional Scraper Lambda deployed (with `BRAVE_SEARCH_API_KEY` if web enrichment is desired).
- [ ] **Cognito**: Test user created and password set (e.g. `verygreat@test.com` / `VeryGreat123!`).
- [ ] **API**: `terraform output -raw api_gateway_url` returns the correct URL; test with `scripts/call-api-llm.ps1` or Postman.
- [ ] **Frontend**: Either run locally (`npm run dev`) with `.env.local` or deploy to Amplify with env vars set.
- [ ] **Data**: Athena has data for at least one L2 category (e.g. Skincare) for the last 30 days so the report returns products.

### Demo Flow

1. Open the app (local or Amplify URL).
2. Log in with the test user.
3. Enter: “What are the top trending products in Skincare?” (or choose **Skincare** from the dropdown) → **Get report**.
4. Confirm: report appears with products, images, brand URLs, descriptions, supporting trends; **Download PDF** works if `pdf_url` is present.
5. If Scraper is enabled: confirm product links and images look correct (web-enriched).
6. Sign out and optionally show login error handling (wrong password, etc.).

### Documents to Share

- This document (Frontend & Deployment).
- [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) (includes Web Search / Scraper Lambda).
- [terraform/README-LLM.md](../terraform/README-LLM.md) for infrastructure and Lambda deployment.
- [docs/INDEX.md](INDEX.md) for the full documentation index.

---

## Troubleshooting

### "VITE_API_URL is not set"

- Ensure `VITE_API_URL` is in `frontend/.env.local` (local) or in Amplify environment variables (hosted). Rebuild after changing env vars in Amplify.

### "Not authenticated. Sign in again."

- User session expired or not logged in. Sign in again; ensure Cognito User Pool ID and Client ID match the backend.

### CORS or network errors when calling the API

- Confirm API Gateway CORS allows the frontend origin (e.g. `https://main.xxxxx.amplifyapp.com` or `http://localhost:5173` for dev).
- Confirm `VITE_API_URL` is exactly the URL of the API Gateway stage (including `/trending-products/query`).

### Report shows "Error" with backend message

- Check `request_id` and CloudWatch logs for the Orchestrator Lambda. Use [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) and [terraform/README-LLM.md](../terraform/README-LLM.md) for backend troubleshooting.

### No products / empty report

- Backend may return “No trending products” if there is no data in Athena for the category/period or quality filters. Verify data in Athena and that the Lambda has access to the Glue table and S3 data.

---

**Last Updated:** February 4, 2026  
**Maintained By:** Data Engineering / Frontend Team
