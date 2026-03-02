# LLM Trending Products — Frontend Access Guide

**Version:** 2.0.0  
**Last Updated:** February 26, 2026

---

## Application URL

**Production URL:** https://amplify-versio.d32yhcl4pif1yr.amplifyapp.com/

The application is hosted on AWS Amplify and requires no installation. Access it from any modern web browser (Chrome, Firefox, Edge, Safari).

---

## Demo / Test Account

| Field    | Value                  |
|----------|------------------------|
| Email    | `verygreat@test.com`   |
| Password | `VeryGreat123!`        |

> **Note:** This is a shared demo account for POC testing. For production use, create individual user accounts per the instructions below.

---

## How to Use the Application

### 1. Sign In

1. Open the URL above
2. Enter the email and password
3. Click **Sign In**

### 2. Generate a Report

1. Select an **L2 Category** from the dropdown (e.g. *Skincare*, *Makeup*, *Hair Care*), or type a free-text query in the search box (e.g. *"What are the top trending products in Skincare?"*)
2. Click **Get Report**
3. The system will process the request in the background (~15–25 seconds)

### 3. View Results

The report displays:
- **Market Context:** Top 5 real products by revenue for the selected category (last 30 days)
- **Brand Proposal:** An AI-generated brand concept inspired by market leaders (name, tagline, story, values, positioning)
- **Product Ideas:** 5 AI-generated product concepts with descriptions, estimated price, key ingredients, competitive advantage, and AI-generated concept images
- **Download PDF:** A professional PDF report with all content and images

---

## How Report Generation Works (Technical Reference)

The system uses an **asynchronous flow**:

1. **POST** `/trending-products/query` → returns `202 Accepted` with a `request_id` immediately
2. The Lambda runs in the background: queries Athena → generates brand via Bedrock Nova Pro → generates 5 product ideas → generates images via Stability SD 3.5 → creates PDF
3. The frontend polls **GET** `/report/{request_id}` until `status` changes from `"processing"` to `"completed"` or `"failed"`
4. On `completed`, the frontend renders the full report and PDF download link

PDF links are valid for **1 hour**. After that, re-generate the report to get a new link.

---

## Creating Additional User Accounts

Each user needs an account in the AWS Cognito User Pool. User accounts can be managed via the AWS Console or CLI.

### Via AWS Console

1. Go to **AWS Console** → **Cognito** → **User pools** → find the pool named `beauty-products-trending-{environment}`
2. Click **Users** → **Create user**
3. Set email as username, enter a temporary password, and check **Send an email invitation** if desired
4. The user will be prompted to set a new password on first login

### Via AWS CLI

```powershell
# Get User Pool ID from Terraform outputs
cd terraform
$USER_POOL_ID = terraform output -raw cognito_user_pool_id

# Create user
aws cognito-idp admin-create-user `
  --user-pool-id $USER_POOL_ID `
  --username new.user@example.com `
  --user-attributes Name=email,Value=new.user@example.com `
  --temporary-password "TempPass123!" `
  --message-action SUPPRESS

# Set permanent password immediately (optional — skips forced reset)
aws cognito-idp admin-set-user-password `
  --user-pool-id $USER_POOL_ID `
  --username new.user@example.com `
  --password "PermanentPass123!" `
  --permanent
```

Password requirements: minimum 8 characters, at least one uppercase letter, one lowercase letter, and one number.

---

## Troubleshooting

| Symptom | Likely Cause | Solution |
|---------|-------------|----------|
| Can't sign in | Wrong credentials | Verify email/password; check Caps Lock |
| Report stuck on "processing" | Lambda cold start or Bedrock throttle | Wait up to 45 seconds; refresh and try again |
| "Category not found" error | No data for selected category in last 30 days | Choose a different category or upload fresh data |
| PDF link expired | Presigned URL is valid for 1 hour only | Re-run the query to generate a new report |
| Blank page after login | Browser cache issue | Hard refresh (Ctrl+Shift+R) or use incognito mode |

For detailed troubleshooting, see [`runbooks/`](../runbooks/) or contact your system administrator.

---

## Support Contacts

- **Technical issues:** Refer to the [Operations Guide](CLIENT-OPERATIONS-GUIDE.md)
- **User management:** AWS Console → Cognito
- **System monitoring:** AWS Console → CloudWatch → Dashboards → `beauty-products-llm-dashboard`
