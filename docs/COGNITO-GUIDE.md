# AWS Cognito Guide
## Authentication and authorization for the LLM Trending Products system

**Version:** 1.0.0  
**Last Updated:** March 2, 2026  
**Maintained By:** Revstar DATA AI Team

---

## Overview

The project uses **Amazon Cognito** as the identity provider for:

- **Authentication** of frontend users (React/Amplify) and clients calling the REST API.
- **Authorization** at API Gateway: all LLM routes (`/trending-products/*`) require a valid JWT issued by the Cognito User Pool.

This document describes how Cognito is configured, how it integrates with the rest of the system, and how to manage users and tokens.

---

## 1. Cognito components

### 1.1 User Pool

- **Terraform resource:** `aws_cognito_user_pool.llm` (defined in `terraform/cognito-llm.tf`).
- **Name:** `beauty-products-trending-users-{environment}` (e.g. `beauty-products-trending-users-poc`).

**Main configuration:**

| Aspect | Configuration |
|--------|----------------|
| **Username** | Email (`username_attributes = ["email"]`) |
| **Verification** | Email verified with code (`CONFIRM_WITH_CODE`) |
| **Password policy** | Minimum 8 characters, uppercase, lowercase, number, and symbol |
| **Temporary password** | Valid for 7 days |
| **Account recovery** | Via verified email |
| **MFA** | Off by default (`OFF`); can be enabled for production |
| **Email sending** | `COGNITO_DEFAULT` (Cognito limits) |
| **Advanced security** | `AUDIT` mode (audit only) |

### 1.2 App Client

- **Terraform resource:** `aws_cognito_user_pool_client.llm`.
- **Name:** `beauty-products-trending-client-{environment}`.

**Main configuration:**

| Aspect | Value |
|--------|--------|
| **Access token** | 1 hour |
| **Id token** | 1 hour |
| **Refresh token** | 30 days |
| **Secret** | No (`generate_secret = false`) for web/mobile clients |
| **Auth flows** | `USER_PASSWORD_AUTH`, `REFRESH_TOKEN_AUTH`, `USER_SRP_AUTH` |
| **Prevent user existence errors** | `ENABLED` |

The **IdToken** is what is sent as `Authorization: Bearer <IdToken>` to the API.

### 1.3 Domain (Hosted UI)

- **Terraform resource:** `aws_cognito_user_pool_domain.llm`.
- **Domain:** `{cognito_domain_prefix}-{environment}` (e.g. `beauty-products-trending-poc-poc` if the prefix includes the env).

The prefix is set in `terraform.tfvars` via the `cognito_domain_prefix` variable and **must be unique across the AWS account**. If you see *"Domain already exists"*, change that value.

---

## 2. API Gateway integration

- **Authorizer:** type `COGNITO_USER_POOLS`, linked to the User Pool above.
- **Protected resources:** all methods under `/trending-products` (GET categories, POST query, GET report/{request_id}, etc.) use this authorizer.

Summary flow:

1. The client obtains an IdToken from Cognito (login with username/password or refresh).
2. It sends requests with `Authorization: Bearer <IdToken>`.
3. API Gateway validates the JWT with Cognito (and may cache the result).
4. If the token is valid, the request reaches Lambda; otherwise, 401 is returned.

Cognito groups are not used for API authorization; any authenticated User Pool user can call the protected endpoints.

---

## 3. Frontend integration (React/Amplify)

The frontend uses **AWS Amplify v6** for Auth only, with the same User Pool and App Client as the API.

**Config file:** `frontend/src/aws-config.ts`

- Reads `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID` (from `.env.local` or build-time env vars).
- Configures `Amplify.configure({ Auth: { Cognito: { ... } } })` with email login.

**Environment variables (frontend):**

| Variable | Recommended source | Description |
|----------|--------------------|-------------|
| `VITE_COGNITO_USER_POOL_ID` | `terraform output -raw cognito_user_pool_id` | User Pool ID |
| `VITE_COGNITO_CLIENT_ID` | `terraform output -raw cognito_client_id` | App Client ID |
| `VITE_AWS_REGION` | Optional, default `us-east-1` | Cognito region |

If User Pool ID or Client ID are missing, the frontend logs a console warning and authentication will not work.

Login flow in the app (including handling `NEW_PASSWORD_REQUIRED` for temporary passwords) is documented in [frontend/README.md](../frontend/README.md) and [AMPLIFY-CLIENT-LINK.md](AMPLIFY-CLIENT-LINK.md).

---

## 4. Terraform variables and outputs

### Variables (Cognito)

| Variable | Description | Example / default |
|----------|-------------|--------------------|
| `enable_llm_system` | If `true`, User Pool, Client, and domain are created | `true` |
| `cognito_domain_prefix` | Cognito domain prefix (unique in AWS) | `beauty-products-trending-poc` |

Defined in `terraform/variables.tf` and set in `terraform/terraform.tfvars`.

### Outputs

From the `terraform/` directory:

```bash
terraform output -raw cognito_user_pool_id    # User Pool ID
terraform output -raw cognito_client_id        # App Client ID
terraform output -raw cognito_user_pool_domain # Hosted UI domain
terraform output -raw cognito_user_pool_endpoint
terraform output -raw cognito_user_pool_arn
```

These values are used to configure the frontend, test scripts, and operations documentation.

---

## 5. User management

### 5.1 Create test user (once per environment)

From the project root or `terraform/`:

```powershell
cd terraform
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

aws cognito-idp admin-create-user `
  --user-pool-id $USER_POOL_ID `
  --username verygreat@test.com `
  --user-attributes Name=email,Value=verygreat@test.com `
  --temporary-password "TempPass123!" `
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password `
  --user-pool-id $USER_POOL_ID `
  --username verygreat@test.com `
  --password "VeryGreat123!" `
  --permanent
```

Password requirements: minimum 8 characters, at least one uppercase, one lowercase, one number, and one symbol.

### 5.2 Create another user

Replace `user@example.com` and the password with the desired values:

```powershell
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

aws cognito-idp admin-create-user `
  --user-pool-id $USER_POOL_ID `
  --username user@example.com `
  --user-attributes Name=email,Value=user@example.com `
  --temporary-password "TempPass123!" `
  --message-action SUPPRESS

aws cognito-idp admin-set-user-password `
  --user-pool-id $USER_POOL_ID `
  --username user@example.com `
  --password "PermanentPass123!" `
  --permanent
```

### 5.3 List users

```powershell
$USER_POOL_ID = (cd terraform; terraform output -raw cognito_user_pool_id)
aws cognito-idp list-users --user-pool-id $USER_POOL_ID `
  --query "Users[*].{Username:Username,Status:UserStatus,Created:UserCreateDate}"
```

### 5.4 Disable or delete a user

```powershell
# Disable (user cannot sign in; account is kept)
aws cognito-idp admin-disable-user --user-pool-id $USER_POOL_ID --username user@example.com

# Delete permanently
aws cognito-idp admin-delete-user --user-pool-id $USER_POOL_ID --username user@example.com
```

More detail in [CLIENT-OPERATIONS-GUIDE.md](CLIENT-OPERATIONS-GUIDE.md#4-user-management) and [AMPLIFY-CLIENT-LINK.md](AMPLIFY-CLIENT-LINK.md).

---

## 6. Obtaining a token to call the API

### 6.1 From PowerShell (test script)

The script `scripts/call-api-llm.ps1` already obtains the IdToken and calls the API:

- Reads `cognito_user_pool_id`, `cognito_client_id`, and `api_gateway_url` from Terraform.
- Uses user `verygreat@test.com` / `VeryGreat123!` and flow `USER_PASSWORD_AUTH`.
- Sends the IdToken in `Authorization: Bearer <token>`.

Usage: from the project root, `.\scripts\call-api-llm.ps1`.

### 6.2 Manually (AWS CLI)

```powershell
$COGNITO_CLIENT_ID = terraform output -raw cognito_client_id
$authJson = aws cognito-idp initiate-auth `
  --auth-flow USER_PASSWORD_AUTH `
  --client-id $COGNITO_CLIENT_ID `
  --auth-parameters "USERNAME=verygreat@test.com,PASSWORD=VeryGreat123!" `
  --query 'AuthenticationResult.IdToken' `
  --output text
# Use $authJson as Bearer token in HTTP requests
```

### 6.3 From Python (E2E)

The script `scripts/e2e-llm-report.py` gets the IdToken via `boto3` (`cognito-idp`, `initiate_auth` with `USER_PASSWORD_AUTH`), then POSTs to `/trending-products/query` and GETs `/report/{request_id}`. Default credentials are for `verygreat@test.com`; override with env vars `COGNITO_USERNAME` and `COGNITO_PASSWORD`.

---

## 7. Troubleshooting

| Issue | Likely cause | Solution |
|-------|----------------|----------|
| **Domain already exists** | `cognito_domain_prefix` already in use in AWS | Change `cognito_domain_prefix` in `terraform.tfvars` and re-apply |
| **401 Unauthorized** on the API | Invalid, expired, or missing token | Get a new IdToken with `initiate-auth` and send `Authorization: Bearer <IdToken>` |
| **No IdToken in auth response** | Wrong flow or parameters | Ensure the App Client has `ALLOW_USER_PASSWORD_AUTH` and username/password are correct |
| **User not confirmed** | Email not verified or user in temporary state | Use `admin-set-user-password` with `--permanent` or confirm the user in the Cognito console |
| **Frontend: "AWS config missing"** | Cognito env vars missing | Set `VITE_COGNITO_USER_POOL_ID` and `VITE_COGNITO_CLIENT_ID` (e.g. from Terraform outputs) |

For end-to-end testing and validating the Cognito flow, see [runbooks/validation-and-testing.md](../runbooks/validation-and-testing.md) (Auth and Cognito section).

---

## 8. Quick references

- **Cognito infrastructure:** `terraform/cognito-llm.tf`
- **API authorizer:** `terraform/api-gateway-llm.tf` (resource `aws_api_gateway_authorizer.cognito`)
- **Frontend config:** `frontend/src/aws-config.ts`, `frontend/.env.example`
- **Test user and testing:** [terraform/README-LLM.md](../terraform/README-LLM.md#step-1-create-test-user-required-once)
- **Costs:** [COST-BREAKDOWN.md](COST-BREAKDOWN.md) (Cognito in the cost breakdown)

---

**Last Updated:** March 2, 2026
