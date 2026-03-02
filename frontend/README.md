# LLM Trending Products – Frontend

SPA that authenticates with Cognito and calls the LLM Trending Products API (POST `/trending-products/query`). Uses the same User Pool and Client as the backend.

## Prerequisites

- Node.js 18+ and npm
- Backend deployed: Terraform applied, Lambda deployed, Cognito test user (e.g. `verygreat@test.com`) created. See [terraform/README-LLM.md](../terraform/README-LLM.md).
- API and Cognito IDs from Terraform outputs (or AWS Console if Terraform is not used).

## Environment variables

Set these in `frontend/.env.local` for local development, and in Amplify Hosting **Build settings / Environment variables** for production.

| Variable | Description | Source (Terraform) |
|----------|-------------|--------------------|
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID | `terraform output -raw cognito_user_pool_id` |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID | `terraform output -raw cognito_client_id` |
| `VITE_AWS_REGION` | AWS region (same as API Gateway) | e.g. `us-east-1` |
| `VITE_API_URL` | Full API Gateway URL (includes `/trending-products/query`) | `terraform output -raw api_gateway_url` |

Without Terraform: get **User Pool ID** and **Client ID** from AWS Console → Cognito → User pools → your pool → App integration → App client list.

Copy `frontend/.env.example` to `frontend/.env.local` and fill the values. Do not commit `.env.local`.

## Local development

```bash
cd frontend
npm install
npm run dev
```

Then open the URL shown (e.g. `http://localhost:5173`). Sign in with the Cognito test user (e.g. `verygreat@test.com` / `VeryGreat123!`), then run a query (e.g. “What are the top trending products in Skincare?”).

## Build

```bash
cd frontend
npm install
npm run build
```

Output is in `frontend/dist/`.

## Deploy to Amplify Hosting

1. Push the repo (including the `frontend/` folder) to GitHub, GitLab, Bitbucket, or CodeCommit.
2. In **AWS Amplify Console** → **New app** → **Host web app** → connect the repo and branch.
3. **Build settings**
   - **App root**: `frontend` (if the app code is in the `frontend/` directory).
   - **Build command**: `npm run build` (or the value in `frontend/package.json`).
   - **Output directory**: `dist` (Vite default).
4. **Environment variables**: Add `VITE_API_URL`, `VITE_COGNITO_USER_POOL_ID`, `VITE_COGNITO_CLIENT_ID`, and `VITE_AWS_REGION` with the same values used for the backend (dev or prod).
5. Save and deploy. The URL Amplify provides is where users sign in and run trending-product queries.

## Behavior

- **Login**: Email + password via Amplify Auth (Cognito). If the backend returns `NEW_PASSWORD_REQUIRED`, the UI prompts for a new password and completes the challenge.
- **Chat**: Free-text query and/or L2 category selector. “Get report” sends a POST to `VITE_API_URL` with `Authorization: Bearer <IdToken>` and `{ "query": "…" }`. Results show products, request_id, execution_time_ms, product_count, and “Download PDF” when `pdf_url` is present. On error, the UI shows the backend `message`, `request_id`, and `supported_categories` when provided.

## Tech stack

- Vite + React + TypeScript
- aws-amplify v6 (Auth only, existing Cognito User Pool / Client)
- react-router-dom
