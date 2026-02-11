# Generate Client Link via AWS Amplify Hosting

**Purpose:** Deploy the LLM Trending Products frontend to AWS Amplify Hosting so the client can access the application via a public URL (e.g. `https://amplify_versio.xxxxx.amplifyapp.com`).

**Repository:** [very-great-llms-trends](https://github.com/cradaca39revstar/very-great-llms-trends)  
**Branch used for hosting:** `amplify_versio`

---

## Prerequisites

- Backend already deployed: Terraform applied, Lambda orchestrator deployed, Cognito User Pool and API Gateway in place.
- At least one Cognito test user created (for client login).
- Terraform outputs available (run from `terraform/` directory after `terraform apply`).

---

## Step 1: Get Backend Values (Terraform Outputs)

From the project root, run (PowerShell or Bash):

```powershell
cd terraform
terraform output -raw cognito_user_pool_id
terraform output -raw cognito_client_id
terraform output -raw api_gateway_url
```

Note the values. You will need:

| Output | Use |
|--------|-----|
| `cognito_user_pool_id` | `VITE_COGNITO_USER_POOL_ID` in Amplify |
| `cognito_client_id` | `VITE_COGNITO_CLIENT_ID` in Amplify |
| `api_gateway_url` | `VITE_API_URL` in Amplify (must include `/trending-products/query`) |

Region is usually `us-east-1` (or whatever `terraform.tfvars` uses for `aws_region`).

---

## Step 2: Connect Repository to AWS Amplify

1. Open **AWS Console** → **AWS Amplify**.
2. Click **New app** → **Host web app**.
3. Choose **GitHub** (or your Git provider) and authorize if needed.
4. Select:
   - **Repository:** `cradaca39revstar/very-great-llms-trends`
   - **Branch:** `amplify_versio`
5. Click **Next**.

---

## Step 3: Configure Build Settings

1. **Application root:** Set to `frontend` (the app lives in the `frontend/` folder).
2. Amplify will detect `frontend/amplify.yml` if present. If not, set manually:
   - **Build command:** `npm run build`
   - **Output directory:** `dist`
3. Click **Next**.

---

## Step 4: Add Environment Variables

In **Environment variables** (or after app creation: **App settings** → **Environment variables**), add:

| Name | Value |
|------|--------|
| `VITE_COGNITO_USER_POOL_ID` | Output of `terraform output -raw cognito_user_pool_id` |
| `VITE_COGNITO_CLIENT_ID` | Output of `terraform output -raw cognito_client_id` |
| `VITE_AWS_REGION` | `us-east-1` (or your API region) |
| `VITE_API_URL` | Output of `terraform output -raw api_gateway_url` (full URL including `/trending-products/query`) |

Save. These are required so the frontend can authenticate with Cognito and call the API.

---

## Step 5: Deploy and Get the Client Link

1. Click **Save and deploy** (or **Next** until deployment starts).
2. Wait for the build to complete (install → build → deploy).
3. When the build succeeds, Amplify shows the **live URL**, e.g.:
   - `https://amplify_versio.xxxxxxxxxx.amplifyapp.com`
   - or `https://main.xxxxxxxxxx.amplifyapp.com` if the branch is mapped to "main" in Amplify.

**This URL is the client link.** Share it with the client so they can open the app, sign in with the Cognito user, and run trending-product reports.

---

## Step 6: CORS (If Needed)

API Gateway is typically configured with permissive CORS (`Access-Control-Allow-Origin: *`) in this project. If the client uses a custom domain for Amplify, add that origin to the API Gateway CORS configuration in Terraform (see [FRONTEND-AND-DEPLOYMENT.md](FRONTEND-AND-DEPLOYMENT.md#5-cors)).

---

## Step 7: Client Test Flow

1. Open the Amplify URL in a browser.
2. Sign in with the Cognito test user (email/password).
3. Enter a query (e.g. "What are the top trending products in Skincare?") or choose a category → **Get report**.
4. Confirm the report loads and **Download PDF** works.

---

## Troubleshooting

| Issue | Action |
|-------|--------|
| Build fails (e.g. `npm ci` or `npm run build`) | Check build logs in Amplify; ensure `frontend/package.json` and `frontend/amplify.yml` are on branch `amplify_versio`. |
| "VITE_API_URL is not set" | Add all four `VITE_*` environment variables in Amplify and **redeploy** (env vars are baked in at build time). |
| CORS or network errors when calling API | Verify `VITE_API_URL` is correct and API Gateway CORS allows the Amplify origin. |
| Login fails | Confirm `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID` match the Terraform-deployed User Pool and App Client. |

---

## Related Documentation

- [FRONTEND-AND-DEPLOYMENT.md](FRONTEND-AND-DEPLOYMENT.md) – Frontend stack, env vars, local dev, and handoff checklist.
- [terraform/README-LLM.md](../terraform/README-LLM.md) – Backend and Lambda deployment.
- [LLM-TRENDING-PRODUCTS-ARCHITECTURE.md](LLM-TRENDING-PRODUCTS-ARCHITECTURE.md) – System architecture and API flow.
